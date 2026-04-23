from pydantic import BaseModel
from typing import Optional


class DeliveryConfirmResult(BaseModel):
    """Step3.1 确认结果"""
    count: int
    can_proceed: bool


class DeliveryTaskResult(BaseModel):
    """Step3 创建任务结果"""
    task_name: str
    short_play_id: str
    success: bool
    error_message: Optional[str] = None
