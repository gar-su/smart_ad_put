import json
from datetime import date, timedelta
from pathlib import Path
from src.auto_delivery.api.material import MaterialReportApi
from src.auto_delivery.models.material import QualifiedMaterial


class MaterialService:
    def __init__(self, api: MaterialReportApi | None = None):
        self.api = api or MaterialReportApi()

    def _rate_over_100(self, item: dict) -> bool:
        """判断达标率是否大于100"""
        rate_str = item.get("meetStandardRate", "0%")
        rate = float(rate_str.rstrip("%"))
        return rate > 100

    def _cost_increasing(self, item: dict, yesterday_cost: float | None) -> bool:
        """判断消耗是否提升"""
        if yesterday_cost is None:
            return False
        current_cost = float(item.get("cost", "0"))
        return current_cost > yesterday_cost

    def _parse_material(self, item: dict) -> QualifiedMaterial | None:
        """解析单条素材记录"""
        try:
            if not self._rate_over_100(item):
                return None
            return QualifiedMaterial(
                filename=item["filename"],
                video_name=item["videoName"],
                language_name=item["languageName"],
                material_emp_id=item["materialEmpId"],
                video_id=item["videoId"],
                comprehensive_meet_standard_rate=float(item["comprehensiveMeetStandardRate"].rstrip("%")),
                cost=float(item["cost"]),
            )
        except (KeyError, ValueError):
            return None

    def query_qualified_materials(
        self, days: int = 5, pages_per_day: int = 5, top_per_video: int = 5
    ) -> list[QualifiedMaterial]:
        """查询最近N天达标素材，按达标率排序，每剧取top_per_video个"""
        all_materials: list[QualifiedMaterial] = []
        today = date.today()

        for i in range(days):
            query_date = today - timedelta(days=i)
            for page in range(1, pages_per_day + 1):
                resp = self.api.query_day(query_date, page)
                rows = resp.get("materialCostPage", {}).get("rows", [])
                if not rows:
                    break
                for item in rows:
                    material = self._parse_material(item)
                    if material:
                        all_materials.append(material)

        # 按video_id分组，每组按达标率降序排列，取前top_per_video个
        video_groups: dict[str, list[QualifiedMaterial]] = {}
        for m in all_materials:
            if m.video_id not in video_groups:
                video_groups[m.video_id] = []
            video_groups[m.video_id].append(m)

        # 每组内按达标率降序排序，取前top_per_video个
        result: list[QualifiedMaterial] = []
        for video_id, materials in video_groups.items():
            materials.sort(key=lambda m: m.comprehensive_meet_standard_rate, reverse=True)
            result.extend(materials[:top_per_video])

        # 整体按达标率降序排列
        result.sort(key=lambda m: m.comprehensive_meet_standard_rate, reverse=True)
        return result

    def save_to_file(self, materials: list[QualifiedMaterial], output_path: Path) -> None:
        """保存达标素材到文件"""
        data = [m.model_dump() for m in materials]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, input_path: Path) -> list[QualifiedMaterial]:
        """从文件加载达标素材"""
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        return [QualifiedMaterial(**item) for item in data]
