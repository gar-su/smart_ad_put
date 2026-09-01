"""建造信号模块（对外契约，下游 machine-delivery 消费）"""

from .config import DEFAULT_FOLLOW_UP_STAGES, SignalRules, available_stages
from .generator import BuildSignalGenerator
from .mapper import StageSignalMapper
from .models import BuildSignal, SignalTargetDimension, SignalType

__all__ = [
    "BuildSignal",
    "SignalTargetDimension",
    "SignalType",
    "SignalRules",
    "DEFAULT_FOLLOW_UP_STAGES",
    "available_stages",
    "StageSignalMapper",
    "BuildSignalGenerator",
]
