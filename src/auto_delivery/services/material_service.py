import json
from datetime import date, timedelta
from pathlib import Path
from src.auto_delivery.api.material import MaterialReportApi
from src.auto_delivery.models.material import QualifiedMaterial


class MaterialService:
    def __init__(self, api: MaterialReportApi | None = None):
        self.api = api or MaterialReportApi()

    def _rate_over_100(self, item: dict) -> bool:
        """判断综合达标率是否大于100"""
        rate_str = item.get("comprehensiveMeetStandardRate", "0%")
        rate = float(rate_str.rstrip("%"))
        return rate > 100

    def _cost_increasing(self, item: dict, yesterday_cost: float | None) -> bool:
        """判断消耗是否提升"""
        if yesterday_cost is None:
            return False
        current_cost = float(item.get("cost", "0"))
        return current_cost > yesterday_cost

    def _parse_material(self, item: dict, yesterday_cost: float | None = None) -> QualifiedMaterial | None:
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
                cost_yesterday=yesterday_cost,
            )
        except (KeyError, ValueError):
            return None

    def query_qualified_materials(self, days: int = 5) -> list[QualifiedMaterial]:
        """查询最近N天达标素材"""
        all_materials: list[QualifiedMaterial] = []
        today = date.today()

        for i in range(days):
            query_date = today - timedelta(days=i)
            resp = self.api.query_day(query_date)
            rows = resp.get("materialCostPage", {}).get("rows", [])

            yesterday_cost_map: dict[str, float] = {}
            if i > 0:
                yesterday_date = today - timedelta(days=i - 1)
                yesterday_resp = self.api.query_day(yesterday_date)
                yesterday_rows = yesterday_resp.get("materialCostPage", {}).get("rows", [])
                for row in yesterday_rows:
                    yesterday_cost_map[row["filename"]] = float(row.get("cost", "0"))

            for item in rows:
                material = self._parse_material(item, yesterday_cost_map.get(item["filename"]))
                if material and self._cost_increasing(item, yesterday_cost_map.get(item["filename"])):
                    all_materials.append(material)

        return all_materials

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
