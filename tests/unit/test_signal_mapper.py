"""阶段 → 信号 映射测试（PRD §5.5.2 配置驱动）"""

import pytest

from src.core.lifecycle.stages import Stage
from src.core.signal.config import DEFAULT_FOLLOW_UP_STAGES
from src.core.signal.mapper import StageSignalMapper
from src.core.signal.models import SignalType


def test_default_mapper_maps_all_default_stages():
    """默认阶段列表全部映射为 FOLLOW_UP"""
    mapper = StageSignalMapper()
    for name in DEFAULT_FOLLOW_UP_STAGES:
        assert mapper.map_stage(Stage(name)) is SignalType.FOLLOW_UP


def test_mapper_ignores_non_follow_up_stage():
    """未配置的阶段不产出信号"""
    mapper = StageSignalMapper()
    assert mapper.map_stage(Stage.CAMPAIGN_OBSERVING) is None
    assert mapper.map_stage(Stage.PRODUCT_EXIT) is None


def test_custom_stages_override_defaults():
    """配置注入覆盖默认列表"""
    mapper = StageSignalMapper(stages=["campaign_verify"])
    assert mapper.map_stage(Stage.CAMPAIGN_VERIFY) is SignalType.FOLLOW_UP
    assert mapper.map_stage(Stage.CAMPAIGN_GROWTH) is None  # 默认阶段已不跟投


def test_invalid_stage_name_fails_fast():
    """非法阶段名立即抛 ValueError（配置错误尽早暴露）"""
    with pytest.raises(ValueError):
        StageSignalMapper(stages=["not_a_stage"])
