"""建造信号模型（对外契约）

与 machine-delivery 对齐的信号字段（PRD §5.5.3）。
信号不带 scale —— 放量规模由下游模板承载，本系统只给意图。
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """建造信号类型（本期仅实现 FOLLOW_UP，其余挂起）"""

    FOLLOW_UP = "FOLLOW_UP"  # 跟投：目标值得继续投 → 下游新建放量任务
    RECOVER = "RECOVER"  # 恢复：挂起，后续随数据源补齐
    EXPAND = "EXPAND"  # 扩张：挂起
    TEST = "TEST"  # 探索：挂起


class SignalTargetDimension(str, Enum):
    """信号目标维度（对外统一取值，对齐 machine-delivery）"""

    PRODUCT = "product"
    CAMPAIGN = "campaign"
    MATERIAL = "material"


class BuildSignal(BaseModel):
    """建造信号（下游 machine-delivery 消费）"""

    signal_id: str  # 幂等键（YYYYMMDDHHMMSS_目标ID），重复投递不重复建任务
    signal_type: SignalType
    target_dimension: SignalTargetDimension
    target_id: str
    language_code: str  # 下游模板分流必需
    script_no: str = ""  # 目标为短剧时携带剧本编号
    shortplay_name: str = ""
    reason: str = ""
    confidence: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
