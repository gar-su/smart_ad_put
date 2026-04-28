"""
报表系统 API — 短剧每日数据

对应报表系统 Facebook Business API 的 net short剧数据
"""

from datetime import date, timedelta
from ..api.client import ApiClient


class ReportingApi:
    """短剧日报 API"""

    API_PATH = "/prod-api/put/dashboard/video"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def query_day(self, query_date: date, page: int = 1, page_size: int = 50) -> dict:
        """查询某一天的所有短剧数据（分页）"""
        payload = {
            "appType": 1,
            "type": 1,
            "pageNum": page,
            "pageSize": page_size,
            "today": query_date.isoformat(),
            "startDate": query_date.isoformat(),
            "endDate": query_date.isoformat(),
            "createBy": "",
            "deptIds": [],
            "videoIds": [],
            "linkIds": [],
            "shortPlayTypes": [],
            "mediaList": [],
            "language": "",
            "adTimeZoneList": [],
            "channelNos": [],
            "weatherNewShortPlay": "",
            "weatherTestLink": "",
            "startShortPlayPublishTime": "",
            "endShortPlayPublishTime": "",
            "channelNoFilterType": 1,
            "timeRange": [query_date.isoformat(), query_date.isoformat()],
        }
        return self.client.post(self.API_PATH, json=payload)

    def query_day_all_pages(self, query_date: date) -> list[dict]:
        """查询某一天的所有短剧数据（自动翻页，直到 cost=0 的那条为止）"""
        all_rows = []
        page = 1
        page_size = 50

        while True:
            data = self.query_day(query_date, page=page, page_size=page_size)
            day_data = data.get("dayCostCollectVos", {})
            rows = day_data.get("rows", [])

            if not rows:
                break

            all_rows.extend(rows)

            # 如果最后一条 cost=0，说明后面没数据了，停止翻页
            try:
                last_cost = float(rows[-1].get("cost", 0) or 0)
            except (ValueError, TypeError):
                last_cost = 0
            if last_cost == 0:
                break

            total = day_data.get("total", 0)
            if len(all_rows) >= total:
                break

            page += 1

        return all_rows

    def query_top_n_by_cost(self, query_date: date, n: int = 200) -> list[dict]:
        """查询某一天 cost 排名前 N 的短剧（返回已排序）"""
        page_size = 50
        all_rows = []

        page = 1
        while len(all_rows) < n:
            data = self.query_day(query_date, page=page, page_size=page_size)
            day_data = data.get("dayCostCollectVos", {})
            rows = day_data.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            total = day_data.get("total", 0)
            if len(all_rows) >= total:
                break
            page += 1

        # 按 cost 降序，取前 n 条
        sorted_rows = sorted(
            [r for r in all_rows if (float(r.get("cost", 0) or 0)) > 0],
            key=lambda r: float(r.get("cost", 0) or 0),
            reverse=True,
        )
        return sorted_rows[:n]
