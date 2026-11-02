"""阶段 → 信号 映射测试（PRD §5.5.2 配置驱动）"""

import pytest

from src.core.lifecycle.stages import Stage
from src.core.signal.config import DEFAULT_ELIMINATE_STAGES, DEFAULT_FOLLOW_UP_STAGES
from src.core.signal.mapper import StageSignalMapper
from src.core.signal.models import SignalType


def test_default_mapper_maps_all_default_stages():
    """默认阶段列表全部映射为 FOLLOW_UP"""
    mapper = StageSignalMapper()
    for name in DEFAULT_FOLLOW_UP_STAGES:
        assert mapper.map_stage(Stage(name)) is SignalType.FOLLOW_UP


def test_default_mapper_maps_eliminate_stages():
    """默认淘汰阶段映射为 ELIMINATE"""
    mapper = StageSignalMapper()
    for name in DEFAULT_ELIMINATE_STAGES:
        assert mapper.map_stage(Stage(name)) is SignalType.ELIMINATE


def test_mapper_ignores_unmapped_stage():
    """未配置的阶段不产出信号"""
    mapper = StageSignalMapper()
    assert mapper.map_stage(Stage.CAMPAIGN_OBSERVING) is None
    assert mapper.map_stage(Stage.PRODUCT_OBSERVING) is None


def test_custom_stages_override_defaults():
    """配置注入覆盖默认列表"""
    mapper = StageSignalMapper(follow_up_stages=["campaign_verify"])
    assert mapper.map_stage(Stage.CAMPAIGN_VERIFY) is SignalType.FOLLOW_UP
    assert mapper.map_stage(Stage.CAMPAIGN_GROWTH) is None  # 默认阶段已不跟投


def test_invalid_stage_name_fails_fast():
    """非法阶段名立即抛 ValueError（配置错误尽早暴露）"""
    with pytest.raises(ValueError):
        StageSignalMapper(follow_up_stages=["not_a_stage"])


def test_overlapping_stage_lists_fail_fast():
    """同一阶段不能既跟投又淘汰"""
    with pytest.raises(ValueError):
        StageSignalMapper(follow_up_stages=["product_entry"], eliminate_stages=["product_entry"])
