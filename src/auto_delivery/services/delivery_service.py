import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from src.auto_delivery.api.delivery import DeliveryApi
from src.auto_delivery.models.binding import BindingResult
from src.auto_delivery.models.delivery import DeliveryTaskResult


class DeliveryService:
    def __init__(self, api: DeliveryApi | None = None):
        self.api = api or DeliveryApi()

    def build_task_name(self, video_name: str, material_count: int) -> str:
        """构建任务名称: 执行日期_短剧名_素材数量"""
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{date_str}_{video_name}_{material_count}"

    def group_by_video(self, binding_results: list[BindingResult]) -> dict[str, list[BindingResult]]:
        """按shortPlayId分组成功的绑定结果"""
        grouped = defaultdict(list)
        for r in binding_results:
            if r.success:
                grouped[r.video_id].append(r)
        return dict(grouped)

    def confirm_and_create(
        self,
        video_name: str,
        video_id: str,
        material_ids: list[int],
        created_by: str,
        channel_package_id: int | None = None,
    ) -> DeliveryTaskResult:
        """3.1 确认 + 3.2 创建任务"""
        confirm_resp = self.api.confirm(video_name, video_id)
        count = confirm_resp.get("data", 0)

        if count <= 0:
            return DeliveryTaskResult(
                task_name="",
                short_play_id=video_id,
                success=False,
                error_message=f"确认失败: 符合条件的视频数量为 {count}",
            )

        task_name = self.build_task_name(video_name, len(material_ids))
        create_resp = self.api.create_task(
            task_name, video_name, video_id, created_by, channel_package_id
        )

        if create_resp.get("code") == 200:
            return DeliveryTaskResult(
                task_name=task_name,
                short_play_id=video_id,
                success=True,
            )
        else:
            return DeliveryTaskResult(
                task_name=task_name,
                short_play_id=video_id,
                success=False,
                error_message=create_resp.get("message", "创建任务失败"),
            )

    def create_tasks(
        self,
        binding_results: list[BindingResult],
        video_name_map: dict[str, str],
        created_by: str,
    ) -> list[DeliveryTaskResult]:
        """批量创建投放任务"""
        grouped = self.group_by_video(binding_results)
        task_results = []

        for video_id, results in grouped.items():
            material_ids = [r.material_id for r in results]
            video_name = video_name_map.get(video_id, video_id)

            result = self.confirm_and_create(video_name, video_id, material_ids, created_by)
            task_results.append(result)

        return task_results

    def save_results(self, results: list[DeliveryTaskResult], output_path: Path) -> None:
        """保存投放任务结果"""
        data = [r.model_dump() for r in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
