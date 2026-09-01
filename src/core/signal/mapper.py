"""阶段 → 建造信号 映射

PRD §5.5.2。本期仅产出 FOLLOW_UP；material_* 维度挂起；
其余阶段（观察/验证/冷启动/冷死亡/衰退/关停）本期不产出信号，
将来由 RECOVER / TEST 等信号类型承接。
"""

from src.core.lifecycle.stages import Stage

from .config import DEFAULT_FOLLOW_UP_STAGES
from .models import SignalType


class StageSignalMapper:
    """生命周期阶段 → 建造信号类型

    值得跟投的阶段由外部配置注入（config/signal_rules.json），
    不注入时使用内置默认（PRD §5.5.2）。
    """

    def __init__(self, stages: list[str] | None = None) -> None:
        """stages: 值得跟投（FOLLOW_UP）的阶段名列表，非法名立即抛 ValueError"""
        names = stages if stages is not None else DEFAULT_FOLLOW_UP_STAGES
        self._map: dict[Stage, SignalType] = {Stage(name): SignalType.FOLLOW_UP for name in names}

    def map_stage(self, stage: Stage) -> SignalType | None:
        """返回阶段对应的信号类型；无映射则 None（不产出信号）"""
        return self._map.get(stage)
