import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from src.auto_delivery.services.material_service import MaterialService
from src.auto_delivery.services.binding_service import BindingService
from src.auto_delivery.services.delivery_service import DeliveryService
from src.auto_delivery.services.channel_package_service import ChannelPackageService


class AutoDeliveryRunner:
    def __init__(self, output_dir: Path | None = None, credentials_path: Path | None = None):
        # Use parent directory of auto_delivery as base (src/)
        base = Path(__file__).resolve().parent.parent.parent
        self.output_dir = output_dir or (base / "output" / "auto_delivery")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.material_service = MaterialService()
        self.binding_service = BindingService()
        self.delivery_service = DeliveryService()
        self.channel_package_service = ChannelPackageService()

        # Load credentials for created_by
        cred_path = credentials_path or (base / "config" / "credentials.json")
        with open(cred_path) as f:
            creds = json.load(f)
        self.created_by = creds.get("created_by", "2030896251477688321")

    def _get_timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def run(self, days: int = 5) -> dict:
        """执行完整流程"""
        results = {
            "step1_materials_found": 0,
            "step2_bind_success": 0,
            "step2_bind_failed": 0,
            "step3_create_success": 0,
            "step3_create_failed": 0,
            "errors": [],
        }

        # Step 1: 查询达标素材
        print("[Step1] 查询达标素材...")
        materials = self.material_service.query_qualified_materials(days=days)
        results["step1_materials_found"] = len(materials)

        materials_file = self.output_dir / f"step1_materials_{self._get_timestamp()}.json"
        self.material_service.save_to_file(materials, materials_file)
        print(f"[Step1] 找到 {len(materials)} 个达标素材，已保存到 {materials_file}")

        if not materials:
            results["errors"].append("Step1: 没有找到达标素材")
            return results

        # Step 2: 绑定素材
        print("[Step2] 绑定素材到短剧...")
        binding_results = self.binding_service.bind_materials(materials)
        success_bindings = [r for r in binding_results if r.success]
        failed_bindings = [r for r in binding_results if not r.success]
        results["step2_bind_success"] = len(success_bindings)
        results["step2_bind_failed"] = len(failed_bindings)

        bindings_file = self.output_dir / f"step2_bindings_{self._get_timestamp()}.json"
        self.binding_service.save_results(binding_results, bindings_file)
        print(f"[Step2] 绑定成功 {len(success_bindings)} 个，失败 {len(failed_bindings)} 个，已保存到 {bindings_file}")

        if not success_bindings:
            results["errors"].append("Step2: 没有成功绑定的素材")
            return results

        # Step 3: 创建投放任务（按语言分组）
        print("[Step3] 创建广告投放任务（按语言分组）...")

        # 按语言分组成功的绑定结果，同时记录 video_id -> video_name 映射
        language_groups: dict[str, list] = defaultdict(list)
        video_name_map: dict[str, str] = {}
        material_language_map: dict[int, str] = {}  # material_id -> language_code

        for m in materials:
            video_name_map[m.video_id] = m.video_name
            material_language_map[int(m.material_emp_id)] = m.language_code

        # 构建 video_id -> language_code 的映射（从 binding_results）
        # 这里我们假设同一个 video_id 的素材语言相同
        video_language_map: dict[str, str] = {}
        for m in materials:
            video_language_map[m.video_id] = m.language_code

        # 为每种语言获取或创建账户包
        languages_used = set(m.language_code for m in materials)
        language_channel_map: dict[str, int] = {}

        for lang_code in languages_used:
            print(f"[Step3] 获取/创建语言 {lang_code} 的账户包...")
            channel_package_id = self.channel_package_service.get_or_create_by_language(lang_code)
            language_channel_map[lang_code] = channel_package_id
            print(f"[Step3] 语言 {lang_code} -> channelPackageId {channel_package_id}")

        # 按 video_id 分组创建任务
        video_groups: dict[str, list] = defaultdict(list)
        for r in success_bindings:
            video_groups[r.video_id].append(r)

        # 为每个 video_id 创建任务
        task_results = []
        for video_id, bindings in video_groups.items():
            # 获取该视频对应的语言
            lang_code = video_language_map.get(video_id, "en_US")
            channel_package_id = language_channel_map.get(lang_code)

            video_name = video_name_map.get(video_id, video_id)
            material_ids = [r.material_id for r in bindings]

            result = self.delivery_service.confirm_and_create(
                video_name, video_id, material_ids, self.created_by, channel_package_id
            )
            task_results.append(result)

        success_tasks = [r for r in task_results if r.success]
        failed_tasks = [r for r in task_results if not r.success]
        results["step3_create_success"] = len(success_tasks)
        results["step3_create_failed"] = len(failed_tasks)

        tasks_file = self.output_dir / f"step3_tasks_{self._get_timestamp()}.json"
        self.delivery_service.save_results(task_results, tasks_file)
        print(f"[Step3] 创建成功 {len(success_tasks)} 个任务，失败 {len(failed_tasks)} 个，已保存到 {tasks_file}")

        # 汇总
        print("\n=== 执行汇总 ===")
        print(f"Step1: 找到 {results['step1_materials_found']} 个达标素材")
        print(f"Step2: 绑定成功 {results['step2_bind_success']} 个，失败 {results['step2_bind_failed']} 个")
        print(f"Step3: 创建成功 {results['step3_create_success']} 个，失败 {results['step3_create_failed']} 个")
        print(f"语言分布: {dict(language_channel_map)}")
        if results["errors"]:
            print(f"错误: {results['errors']}")

        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="自动化投放流程")
    parser.add_argument("--days", type=int, default=5, help="查询天数")
    args = parser.parse_args()

    runner = AutoDeliveryRunner()
    runner.run(days=args.days)


if __name__ == "__main__":
    main()
