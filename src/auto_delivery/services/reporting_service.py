"""
报表数据服务

从报表系统拉取短剧每日数据，聚合后计算分段指标，
供生命周期检测器使用。

支持两种模式:
- 在线模式: 直接查询API获取数据
- 离线模式: 从本地存储加载历史数据
"""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from ..api.reporting import ReportingApi
from ..api.binding import BindingApi


class ReportingService:
    """拉取并聚合短剧日报数据"""

    def __init__(
        self,
        api: ReportingApi | None = None,
        binding_api: BindingApi | None = None,
        data_dir: Path | None = None,
    ):
        self.api = api or ReportingApi()
        self._binding_api = binding_api or BindingApi()
        self._short_play_cache: dict[tuple[str, str], tuple[str, str] | None] = {}

        # 数据存储目录，默认使用项目 data/video_daily 目录
        base = Path(__file__).resolve().parent.parent.parent.parent
        self.data_dir = data_dir or (base / "data" / "video_daily")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def resolve_short_play_id(
        self,
        video_name: str,
        language_code: str,
        video_id: str,
    ) -> tuple[str, str] | tuple[None, None]:
        """
        根据报表的 video_id 解析 binding 系统的 shortPlayId

        逻辑：binding API 按 (video_name, language_code) 模糊查找，
        返回的 shortPlayLibraryId 与报表 video_id 匹配的那条即为正确结果。

        Returns:
            (shortPlayId, shortPlayName) 或 (None, None)
        """
        cache_key = (video_name, language_code)
        if cache_key in self._short_play_cache:
            return self._short_play_cache[cache_key]

        resp = self._binding_api.query_video(video_name, language_code)
        rows = resp.get("rows", [])
        for row in rows:
            library_id = str(row.get("shortPlayLibraryId", ""))
            if library_id == str(video_id):
                short_play_id = row.get("shortPlayId", "")
                short_play_name = row.get("shortPlayName") or video_name
                result = (short_play_id, short_play_name)
                self._short_play_cache[cache_key] = result
                return result

        self._short_play_cache[cache_key] = None
        return None, None

    def _day_file(self, d: date) -> Path:
        """获取某日数据文件路径"""
        return self.data_dir / f"{d.isoformat()}.json"

    def fetch_and_store_day(self, query_date: date, page_size: int = 50) -> list[dict]:
        """
        查询并存储单日数据到本地文件（只查第一页）

        Args:
            query_date: 查询日期
            page_size: 每页大小，默认 50

        Returns:
            该日所有短剧数据行
        """
        data = self.api.query_day(query_date, page=1, page_size=page_size)
        rows = data.get("dayCostCollectVos", {}).get("rows", [])

        # 存储到 {data_dir}/{date}.json
        day_file = self._day_file(query_date)
        with open(day_file, "w", encoding="utf-8") as f:
            json.dump({
                "date": query_date.isoformat(),
                "rows": rows,
                "count": len(rows),
            }, f, ensure_ascii=False, indent=2)

        print(f"[ReportingService] 已存储 {query_date} -> {day_file} ({len(rows)} 条)")
        return rows

    def load_stored_day(self, query_date: date) -> list[dict] | None:
        """
        从本地加载单日数据

        Args:
            query_date: 查询日期

        Returns:
            该日所有短剧数据行，若不存在返回 None
        """
        day_file = self._day_file(query_date)
        if not day_file.exists():
            return None

        with open(day_file, encoding="utf-8") as f:
            data = json.load(f)

        return data.get("rows", [])

    def load_stored_days(self, start_date: date, end_date: date) -> dict[str, list[dict]]:
        """
        加载指定日期范围内所有已存储的数据

        Args:
            start_date: 开始日期（包含）
            end_date: 结束日期（包含）

        Returns:
            {date_str: [rows...]} 字典，按日期排序
        """
        result: dict[str, list[dict]] = {}
        current = start_date
        while current <= end_date:
            rows = self.load_stored_day(current)
            if rows is not None:
                result[current.isoformat()] = rows
            current += timedelta(days=1)
        return result

    def fetch_and_store_range(
        self,
        start_date: date,
        end_date: date,
        skip_existing: bool = True,
    ) -> dict[str, list[dict]]:
        """
        批量查询并存储日期范围内的数据

        Args:
            start_date: 开始日期（包含）
            end_date: 结束日期（包含）
            skip_existing: 若数据已存在是否跳过，默认 True

        Returns:
            {date_str: [rows...]} 字典
        """
        result: dict[str, list[dict]] = {}
        current = start_date
        while current <= end_date:
            day_file = self._day_file(current)

            if skip_existing and day_file.exists():
                print(f"[ReportingService] 跳过已存储 {current}")
                rows = self.load_stored_day(current)
                if rows:
                    result[current.isoformat()] = rows
            else:
                print(f"[ReportingService] 查询 {current}...")
                rows = self.fetch_and_store_day(current)
                result[current.isoformat()] = rows

            current += timedelta(days=1)

        return result

    def fetch_and_aggregate(
        self,
        days: int = 7,
        top_n: int = 200,
        target_date: date | None = None,
        use_stored: bool = True,
    ) -> list[dict]:
        """
        拉取最近 N 天数据，聚合后返回带分段指标的短剧列表

        Args:
            days: 聚合天数，默认 7 天
            top_n: 每天按 cost 取前 N 条，默认 200
            target_date: 截止日期，默认昨天
            use_stored: 若为 True，优先从本地存储加载数据，只在数据不存在时查询API

        Returns:
            list[dict]，每条包含:
            - video_id: 短剧 ID
            - video_name: 短剧名称
            - language: 语言
            - duration_hours: 投放时长（天数 * 24）
            - total_revenue: 总收入（7天累加）
            - total_cost: 总成本（7天累加）
            - roi: 总 ROI
            - revenue_0_24h / cost_0_24h: 首日收入/成本
            - revenue_24_72h / cost_24_72h: 次日+第3天累加
            - revenue_72plus / cost_72plus: 第4天起累加
            - daily_data: list[dict] 每日明细（原始）
        """
        end_date = target_date or (date.today() - timedelta(days=1))

        # 每天拉 top_n，按 (videoId, language) 分组 = 短剧维度
        daily_by_video: dict[tuple[str, str], list[tuple[date, dict]]] = defaultdict(list)

        for i in range(days):
            d = end_date - timedelta(days=i)

            # 优先从本地存储加载
            if use_stored:
                rows = self.load_stored_day(d)
                if rows is None:
                    # 存储中没有，先存储全部数据，再取 top_n
                    rows = self.fetch_and_store_day(d)
                # 从存储加载后（或刚存储的），按 cost 降序取 top_n
                rows = sorted(
                    [r for r in rows if float(r.get("cost", 0) or 0) > 0],
                    key=lambda r: float(r.get("cost", 0) or 0),
                    reverse=True,
                )[:top_n]
            else:
                # 在线模式：只查第一页
                data = self.api.query_day(d, page=1, page_size=top_n)
                rows = data.get("dayCostCollectVos", {}).get("rows", [])
                rows = sorted(
                    [r for r in rows if float(r.get("cost", 0) or 0) > 0],
                    key=lambda r: float(r.get("cost", 0) or 0),
                    reverse=True,
                )[:top_n]

            for row in rows:
                video_id = str(row.get("videoId", ""))
                raw_language = row.get("language", "")
                if video_id and raw_language:
                    daily_by_video[(video_id, raw_language)].append((d, row))

        # 聚合
        aggregated = []
        for (video_id, raw_language), day_entries in daily_by_video.items():
            # 按日期排序（最早在前）
            day_entries.sort(key=lambda x: x[0])

            if not day_entries:
                continue

            # 累加
            total_revenue = 0.0
            total_cost = 0.0
            revenue_0_24h = 0.0
            cost_0_24h = 0.0
            revenue_24_72h = 0.0
            cost_24_72h = 0.0
            revenue_72plus = 0.0
            cost_72plus = 0.0

            for idx, (d, row) in enumerate(day_entries):
                revenue = self._parse_income(row)
                cost = self._parse_cost(row)

                total_revenue += revenue
                total_cost += cost

                # 首日
                if idx == 0:
                    revenue_0_24h = revenue
                    cost_0_24h = cost
                # 第2、3天
                elif idx <= 2:
                    revenue_24_72h += revenue
                    cost_24_72h += cost
                # 第4天起
                else:
                    revenue_72plus += revenue
                    cost_72plus += cost

            duration_hours = len(day_entries) * 24
            video_name = day_entries[0][1].get("videoName", "")
            lang_code = self._map_language(raw_language)

            # 解析 shortPlayId
            short_play_id, short_play_name = self.resolve_short_play_id(
                video_name, lang_code, video_id
            )

            aggregated.append({
                "video_id": video_id,
                "short_play_id": short_play_id,
                "short_play_name": short_play_name or video_name,
                "video_name": video_name,
                "language": raw_language,
                "language_code": lang_code,
                "duration_hours": duration_hours,
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "roi": total_revenue / total_cost if total_cost > 0 else 0,
                "revenue_0_24h": revenue_0_24h,
                "cost_0_24h": cost_0_24h,
                "revenue_24_72h": revenue_24_72h,
                "cost_24_72h": cost_24_72h,
                "revenue_72plus": revenue_72plus,
                "cost_72plus": cost_72plus,
                "daily_data": [
                    {"date": d.isoformat(), "revenue": self._parse_income(r), "cost": self._parse_cost(r)}
                    for d, r in day_entries
                ],
            })

        # 按 total_cost 降序
        aggregated.sort(key=lambda x: x["total_cost"], reverse=True)
        return aggregated

    def _parse_income(self, row: dict) -> float:
        """解析 D0 收入（归因当日新增用户充值收入）"""
        return self._parse_float(row.get("newUserRechargeAmount", 0))

    def _parse_cost(self, row: dict) -> float:
        """解析成本"""
        return self._parse_float(row.get("cost", 0))

    def _map_language(self, raw: str) -> str:
        """将原始语言名映射为语言代码"""
        from ..constants import LANGUAGE_MAP
        return LANGUAGE_MAP.get(raw, raw)

    def _parse_float(self, val) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace("%", "").replace(",", ""))
        except (ValueError, TypeError):
            return 0.0
