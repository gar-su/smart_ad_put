"""阶段 → 建造信号 映射

PRD §5.3.2 + docs/eliminate-signal-requirements.md §4。
本期实现 FOLLOW_UP（跟投）与 ELIMINATE（淘汰）；material_* 维度挂起；
其余阶段（观察/验证/冷启动/冷死亡/关停）不产出信号。
"""

from src.core.lifecycle.stages import Stage

from .config import DEFAULT_ELIMINATE_STAGES, DEFAULT_FOLLOW_UP_STAGES
from .models import SignalType


class StageSignalMapper:
    """生命周期阶段 → 建造信号类型

    跟投与淘汰阶段均由外部配置注入（config/signal_rules.json），
    不注入时使用内置默认。
    """

    def __init__(
        self,
        follow_up_stages: list[str] | None = None,
        eliminate_stages: list[str] | None = None,
    ) -> None:
        """follow_up_stages / eliminate_stages: 阶段名列表，非法名立即抛 ValueError"""
        follow_up = follow_up_stages if follow_up_stages is not None else DEFAULT_FOLLOW_UP_STAGES
        eliminate = eliminate_stages if eliminate_stages is not None else DEFAULT_ELIMINATE_STAGES
        self._map: dict[Stage, SignalType] = {
            Stage(name): SignalType.FOLLOW_UP for name in follow_up
        }
        for name in eliminate:
            stage = Stage(name)
            if stage in self._map:
                raise ValueError(f"阶段 {name} 同时配置为 FOLLOW_UP 与 ELIMINATE")
            self._map[stage] = SignalType.ELIMINATE

    def map_stage(self, stage: Stage) -> SignalType | None:
        """返回阶段对应的信号类型；无映射则 None（不产出信号）"""
        return self._map.get(stage)
