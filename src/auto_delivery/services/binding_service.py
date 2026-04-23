import json
from collections import defaultdict
from pathlib import Path
from src.auto_delivery.api.binding import BindingApi
from src.auto_delivery.models.material import QualifiedMaterial
from src.auto_delivery.models.binding import BindingResult


class BindingService:
    def __init__(self, api: BindingApi | None = None):
        self.api = api or BindingApi()

    def group_by_video(self, materials: list[QualifiedMaterial]) -> dict[str, list[QualifiedMaterial]]:
        """按videoId分组素材"""
        grouped = defaultdict(list)
        for m in materials:
            grouped[m.video_id].append(m)
        return dict(grouped)

    def get_bind_id(self, filename: str) -> int | None:
        """2.1 获取绑定用素材ID"""
        resp = self.api.search_material(filename)
        materials = resp.get("data", {}).get("materials", [])
        if materials:
            return materials[0]["id"]
        return None

    def get_short_play_id(self, video_name: str, language_code: str) -> str | None:
        """2.2 获取绑定用shortPlayId"""
        resp = self.api.query_video(video_name, language_code)
        rows = resp.get("rows", [])
        for row in rows:
            if row.get("shortPlayLibraryId"):
                return row["shortPlayId"]
        return None

    def bind_materials(self, materials: list[QualifiedMaterial]) -> list[BindingResult]:
        """批量绑定素材到短剧"""
        results = []
        for m in materials:
            bind_id = self.get_bind_id(m.filename)
            if not bind_id:
                results.append(BindingResult(
                    material_id=int(m.material_emp_id),
                    video_id=m.video_id,
                    success=False,
                    error_message=f"未找到素材绑定ID: {m.filename}",
                ))
                continue

            short_play_id = self.get_short_play_id(m.video_name, m.language_code)
            if not short_play_id:
                results.append(BindingResult(
                    material_id=bind_id,
                    video_id=m.video_id,
                    success=False,
                    error_message=f"未找到shortPlayId: {m.video_name}",
                ))
                continue

            resp = self.api.bind_material(bind_id, short_play_id)
            if resp.get("code") == 200:
                results.append(BindingResult(
                    material_id=bind_id,
                    video_id=short_play_id,
                    success=True,
                ))
            else:
                results.append(BindingResult(
                    material_id=bind_id,
                    video_id=short_play_id,
                    success=False,
                    error_message=resp.get("message", "绑定失败"),
                ))

        return results

    def save_results(self, results: list[BindingResult], output_path: Path) -> None:
        """保存绑定结果"""
        data = [r.model_dump() for r in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_results(self, input_path: Path) -> list[BindingResult]:
        """加载绑定结果"""
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        return [BindingResult(**item) for item in data]
