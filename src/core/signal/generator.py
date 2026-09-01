"""建造信号生成器

组合 生命周期判定 + 阶段→信号映射 + 信号冷却控制，产出 BuildSignal。

冷却（PRD §5.5.2 触发控制）：同一目标同一信号类型在冷却期内不重复产出。
当前为进程内状态；跨进程持久化由调用方（pipeline）决定，本期不锁实现。
"""

from datetime import UTC, datetime, timedelta
from typing import Callable

from src.core.lifecycle.stages import LifecycleRecord

from .mapper import StageSignalMapper
from .models import BuildSignal, SignalTargetDimension, SignalType


class BuildSignalGenerator:
    """生成建造信号"""

    def __init__(
        self,
        cooldown_hours: int = 24,
        mapper: StageSignalMapper | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.cooldown = timedelta(hours=cooldown_hours)
        self.mapper = mapper or StageSignalMapper()
        self._now = now or (lambda: datetime.now(UTC))
        self._last_sent: dict[tuple[str, SignalType], datetime] = {}

    def generate(
        self,
        lifecycle: LifecycleRecord,
        *,
        language_code: str,
        script_no: str = "",
        shortplay_name: str = "",
    ) -> BuildSignal | None:
        """根据生命周期记录产出建造信号；不满足则 None"""
        signal_type = self.mapper.map_stage(lifecycle.current_stage)
        if signal_type is None:
            return None

        now = self._now()
        key = (lifecycle.entity_id, signal_type)
        last = self._last_sent.get(key)
        if last is not None and now - last < self.cooldown:
            return None

        signal = BuildSignal(
            signal_id=f"{now:%Y%m%d%H%M%S}_{lifecycle.entity_id}",
            signal_type=signal_type,
            target_dimension=SignalTargetDimension(lifecycle.dimension.value),
            target_id=lifecycle.entity_id,
            language_code=language_code,
            script_no=script_no,
            shortplay_name=shortplay_name,
            reason=lifecycle.detection_reason,
            confidence=lifecycle.confidence,
            timestamp=now,
        )
        self._last_sent[key] = now
        return signal
