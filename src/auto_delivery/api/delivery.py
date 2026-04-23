import json
from datetime import datetime
from ..api.client import ApiClient


class DeliveryApi:
    CONFIRM_API_PATH = "/prod-api/batchput/meta/autoTask/selectVideoCount"
    CREATE_API_PATH = "/prod-api/batchput/meta/autoTask/insertOrUpdate"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def confirm(self, short_play_name: str, short_play_id: str) -> dict:
        """3.1 确认接口"""
        condition_value = json.dumps([{"label": short_play_name, "value": short_play_id}])
        params = [{
            "conditionType": 7,
            "conditionRule": 1,
            "conditionValue": condition_value,
        }]
        return self.client.post(self.CONFIRM_API_PATH, json=params)

    def create_task(
        self,
        task_name: str,
        short_play_name: str,
        short_play_id: str,
        created_by: str,
    ) -> dict:
        """3.2 创建投放任务"""
        from ..constants import FIXED_DELIVERY_TASK_PARAMS

        condition_value = json.dumps([{"label": short_play_name, "value": short_play_id}])
        valid_time = json.dumps([{"endTime": "23:59:59", "startTime": "00:00:00"}])
        run_condition = json.dumps([{
            "conditionRule": 1,
            "conditionType": 7,
            "conditionValue": condition_value,
        }])
        stop_condition = json.dumps([
            {"conditionType": 2, "conditionValue": 10},
            {"conditionType": 3, "conditionValue": 10},
        ])

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params = {
            **FIXED_DELIVERY_TASK_PARAMS,
            "taskName": task_name,
            "runConditionList": [{
                "conditionType": 7,
                "conditionRule": 1,
                "conditionValue": condition_value,
            }],
            "validTime": valid_time,
            "runCondition": run_condition,
            "stopCondition": stop_condition,
            "lastFinishTime": now,
            "createdBy": created_by,
            "updatedBy": created_by,
        }
        return self.client.post(self.CREATE_API_PATH, json=params)
