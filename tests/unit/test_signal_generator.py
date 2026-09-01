"""建造信号生成器：mapper 注入 + 冷却控制"""

from datetime import UTC, datetime

from src.core.lifecycle.stages import Dimension, LifecycleRecord, Stage
from src.core.signal.generator import BuildSignalGenerator
from src.core.signal.mapper import StageSignalMapper
from src.core.signal.models import SignalType


def _record(stage: Stage) -> LifecycleRecord:
    return LifecycleRecord(
        dimension=Dimension.PRODUCT,
        entity_id="vid-1",
        current_stage=stage,
        stage_entered_at=datetime.now(UTC),
        detection_reason="测试",
    )


def test_generate_emits_follow_up_for_configured_stage():
    """mapper 命中值得跟投阶段 → 产出 FOLLOW_UP 信号"""
    generator = BuildSignalGenerator(mapper=StageSignalMapper())
    signal = generator.generate(_record(Stage.PRODUCT_ENTRY), language_code="en")
    assert signal is not None
    assert signal.signal_type is SignalType.FOLLOW_UP
    assert signal.target_id == "vid-1"
    assert signal.language_code == "en"


def test_generate_none_for_unconfigured_stage():
    """mapper 未命中 → 不产出信号"""
    generator = BuildSignalGenerator(mapper=StageSignalMapper())
    assert generator.generate(_record(Stage.CAMPAIGN_OBSERVING), language_code="en") is None


def test_custom_mapper_drives_output():
    """外部配置的阶段列表直接决定哪些阶段产出信号"""
    generator = BuildSignalGenerator(mapper=StageSignalMapper(stages=["campaign_verify"]))
    assert generator.generate(_record(Stage.CAMPAIGN_VERIFY), language_code="zh") is not None
    assert generator.generate(_record(Stage.PRODUCT_ENTRY), language_code="zh") is None


def test_cooldown_suppresses_repeat():
    """同目标同类型信号在冷却期内不重复产出"""
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)
    generator = BuildSignalGenerator(cooldown_hours=24, now=lambda: now)
    assert generator.generate(_record(Stage.PRODUCT_ENTRY), language_code="en") is not None
    assert generator.generate(_record(Stage.PRODUCT_ENTRY), language_code="en") is None  # 冷却内
    # 冷却结束后再次产出
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    assert generator.generate(_record(Stage.PRODUCT_ENTRY), language_code="en") is not None
