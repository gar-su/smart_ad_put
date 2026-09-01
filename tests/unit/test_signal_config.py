"""信号规则配置：加载/保存/校验（config/signal_rules.json 单文件配置源）"""

import pytest
from pydantic import ValidationError

from src.core.lifecycle.stages import Stage
from src.core.signal.config import DEFAULT_FOLLOW_UP_STAGES, SignalRules


def test_load_missing_file_returns_defaults(tmp_path):
    """配置缺失时回退内置默认（PRD §5.5.2）"""
    rules = SignalRules.load(tmp_path / "no_such.json")
    assert rules.follow_up_stages == DEFAULT_FOLLOW_UP_STAGES
    assert rules.cooldown_hours == 24


def test_load_roundtrip(tmp_path):
    """保存后再读回，值一致"""
    path = tmp_path / "signal_rules.json"
    rules = SignalRules(follow_up_stages=["campaign_verify"], cooldown_hours=12)
    rules.save(path)
    loaded = SignalRules.load(path)
    assert loaded.follow_up_stages == ["campaign_verify"]
    assert loaded.cooldown_hours == 12


def test_invalid_stage_at_construct_fails():
    """非法阶段名不被接受（pydantic 校验快速失败）"""
    with pytest.raises(ValidationError):
        SignalRules(follow_up_stages=["campaign_verify", "bogus_stage"])


def test_invalid_stage_in_file_fails_on_load(tmp_path):
    """配置文件内出现非法阶段，加载即报错而非运行期炸"""
    path = tmp_path / "signal_rules.json"
    path.write_text('{"follow_up_stages": ["campaign_verify", "bogus"], "cooldown_hours": 24}')
    with pytest.raises(ValidationError):
        SignalRules.load(path)


def test_cooldown_must_be_positive(tmp_path):
    with pytest.raises(ValidationError):
        SignalRules(cooldown_hours=0)


def test_available_stages_excludes_material():
    """可选阶段仅 product_*/campaign_*，本期素材维度无数据支撑"""
    from src.core.signal.config import available_stages

    values = [s["value"] for s in available_stages()]
    assert Stage.PRODUCT_ENTRY.value in values
    assert Stage.CAMPAIGN_GROWTH.value in values
    assert not any(v.startswith("material_") for v in values)
