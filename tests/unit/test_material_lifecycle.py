"""素材维度聚合与生命周期判定测试

素材判定口径（PRD §5.3.4 / 本次策略）：
- 活跃日 = cost > 0 的自然日，零消耗日计入观测跨度但不参与 ROI 序列
- ROI = (订单收入 + 广告收入) / 消耗
- 近 N 日 ROI = 最近 N 个活跃日 的 Σ收入 / Σ消耗
"""

import asyncio
from datetime import date, timedelta

import pytest

from src.core.lifecycle.aggregation import (
    FactValidationError,
    MaterialFact,
    MaterialMetrics,
    aggregate_material,
)
from src.core.lifecycle.detector import (
    DetectionResult,
    LifecycleDetector,
    MaterialLifecycleDetector,
    MaterialSelectionVerdict,
)
from src.core.lifecycle.stages import Dimension, Stage

D0 = date(2026, 7, 1)


def _mf(
    day: int,
    spend: float,
    order: float = 0.0,
    ad: float = 0.0,
    show: int = 1000,
    click: int = 50,
) -> MaterialFact:
    return MaterialFact(
        date=D0 + timedelta(days=day),
        spend=spend,
        income_order=order,
        income_ad=ad,
        impressions=show,
        clicks=click,
    )


# ============================================================
# aggregate_material
# ============================================================


def test_material_zero_spend_days_are_not_active_days() -> None:
    m = aggregate_material(
        [
            _mf(0, 0.0),  # 首投前零消耗，丢弃
            _mf(1, 100.0, 30.0, 10.0),  # roi 0.4
            _mf(2, 0.0),  # 运行中零消耗，丢弃
            _mf(3, 200.0, 60.0, 20.0),  # roi 0.4
            _mf(4, 100.0, 50.0, 0.0),  # roi 0.5
        ]
    )
    assert m.active_days == 3
    assert m.total_cost == 400.0
    assert m.total_revenue == 170.0
    assert m.roi_history == [0.4, 0.4, 0.5]


def test_material_recent_metrics() -> None:
    m = aggregate_material(
        [
            _mf(1, 100.0, 30.0, 10.0),  # roi 0.4
            _mf(2, 200.0, 60.0, 20.0),  # roi 0.4
            _mf(3, 100.0, 50.0, 0.0),  # roi 0.5
        ]
    )
    assert m.recent_3d_roi == pytest.approx(0.425)
    assert m.recent_2d_roi_avg == pytest.approx(0.45)
    assert m.recent_2d_cost_ratio == pytest.approx(0.75)
    assert m.peak_daily_roi == pytest.approx(0.5)


def test_material_ctr_windows() -> None:
    m = aggregate_material(
        [
            _mf(1, 100.0, 50.0, 0.0, show=1000, click=10),
            _mf(2, 100.0, 50.0, 0.0, show=1000, click=20),
            _mf(3, 100.0, 50.0, 0.0, show=1000, click=30),
            _mf(4, 100.0, 50.0, 0.0, show=1000, click=40),
            _mf(5, 100.0, 50.0, 0.0, show=1000, click=50),
        ]
    )
    assert m.recent_2d_ctr == pytest.approx(0.045)
    assert m.prior_3d_ctr == pytest.approx(0.02)


def test_material_selection_metrics() -> None:
    m = aggregate_material(
        [
            _mf(1, 100.0, 50.0),
            _mf(2, 100.0, 60.0),
            _mf(3, 100.0, 70.0),
        ]
    )
    assert m.total_roi == pytest.approx(0.6)
    assert m.avg_daily_cost == pytest.approx(100.0)
    assert m.roi_cv == pytest.approx(0.1361, abs=1e-4)


def test_material_empty_raises() -> None:
    with pytest.raises(FactValidationError, match="为空"):
        aggregate_material([])


def test_material_no_active_days_returns_zero_metrics() -> None:
    m = aggregate_material([_mf(0, 0.0), _mf(1, 0.0)])
    assert m.active_days == 0
    assert m.roi_history == []
    assert m.total_roi == 0.0
    assert m.avg_daily_cost == 0.0
    assert m.roi_cv == 0.0


# ============================================================
# MaterialLifecycleDetector
# ============================================================


def _detect(metrics: MaterialMetrics) -> DetectionResult:
    return MaterialLifecycleDetector().detect(metrics)


def test_material_observing_under_three_active_days() -> None:
    m = aggregate_material([_mf(1, 100.0, 50.0), _mf(2, 100.0, 50.0)])
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_OBSERVING


def test_material_entry_when_recent_roi_above_line_and_cost_not_collapsing() -> None:
    m = aggregate_material(
        [
            _mf(1, 100.0, 40.0, 5.0),
            _mf(2, 100.0, 40.0, 5.0),
            _mf(3, 100.0, 40.0, 5.0),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_ENTRY


def test_material_entry_requires_cost_not_collapsing() -> None:
    # ROI 达标，但近 2 日消耗只占 16.7%，视为放量停滞，不跟投
    m = aggregate_material(
        [
            _mf(1, 100.0, 50.0, 10.0),
            _mf(2, 10.0, 5.0, 1.0),
            _mf(3, 10.0, 5.0, 1.0),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_OBSERVING


def test_material_eliminated_in_entry_window() -> None:
    m = aggregate_material(
        [
            _mf(1, 100.0, 5.0),
            _mf(2, 100.0, 5.0),
            _mf(3, 100.0, 5.0),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_ELIMINATED


def test_material_sustained_after_five_active_days() -> None:
    m = aggregate_material(
        [
            _mf(1, 50.0, 20.0, 2.5),
            _mf(2, 50.0, 20.0, 2.5),
            _mf(3, 100.0, 40.0, 5.0),
            _mf(4, 100.0, 40.0, 5.0),
            _mf(5, 100.0, 40.0, 5.0),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_SUSTAINED


def test_material_fatigue_when_roi_drops_over_half_from_peak() -> None:
    m = aggregate_material(
        [
            _mf(1, 50.0, 40.0),
            _mf(2, 50.0, 40.0),
            _mf(3, 100.0, 30.0),
            _mf(4, 100.0, 20.0),
            _mf(5, 100.0, 20.0),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_FATIGUE


def test_material_fatigue_when_ctr_drops_over_twenty_percent() -> None:
    m = aggregate_material(
        [
            _mf(1, 50.0, 25.0, show=1000, click=50),
            _mf(2, 50.0, 25.0, show=1000, click=50),
            _mf(3, 100.0, 50.0, show=1000, click=50),
            _mf(4, 100.0, 50.0, show=1000, click=30),
            _mf(5, 100.0, 50.0, show=1000, click=30),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_FATIGUE


def test_material_eliminated_takes_priority_at_five_days() -> None:
    m = aggregate_material(
        [
            _mf(1, 50.0, 30.0),
            _mf(2, 50.0, 30.0),
            _mf(3, 100.0, 5.0),
            _mf(4, 100.0, 5.0),
            _mf(5, 100.0, 5.0),
        ]
    )
    result = _detect(m)
    assert result.stage is Stage.MATERIAL_ELIMINATED


def test_detect_material_returns_lifecycle_record() -> None:
    facts = [
        _mf(1, 300.0, 180.0),
        _mf(2, 300.0, 180.0),
        _mf(3, 300.0, 180.0),
    ]
    record = asyncio.run(LifecycleDetector().detect_material("M-001", facts))
    assert record.dimension is Dimension.MATERIAL
    assert record.entity_id == "M-001"
    assert record.current_stage is Stage.MATERIAL_ENTRY
    assert record.metrics_snapshot["active_days"] == 3
    assert record.metrics_snapshot["selected"] is True
    assert "选择通过" in record.metrics_snapshot["selection_reason"]


# ============================================================
# 选品闸门（A 方案）：累计 ROI > 50%、ROI 波动率 <= 0.5、日均消耗 >= 200
# ============================================================


def _select(
    facts: list[MaterialFact], stage: Stage = Stage.MATERIAL_ENTRY
) -> MaterialSelectionVerdict:
    return MaterialLifecycleDetector().select(stage, aggregate_material(facts))


def test_selection_passes_for_profitable_stable_scaled_material() -> None:
    verdict = _select([_mf(1, 300.0, 180.0), _mf(2, 300.0, 180.0), _mf(3, 300.0, 180.0)])
    assert verdict.selected is True
    assert "选择通过" in verdict.reason


def test_selection_rejects_low_total_roi() -> None:
    # 45% 过了 40% 盈利线，但没到 50% 的选品余量
    verdict = _select([_mf(1, 300.0, 135.0), _mf(2, 300.0, 135.0), _mf(3, 300.0, 135.0)])
    assert verdict.selected is False
    assert "累计ROI" in verdict.reason


def test_selection_rejects_volatile_roi() -> None:
    # ROI 分别为 20% / 80% / 120%，均值高但波动过大
    verdict = _select([_mf(1, 300.0, 60.0), _mf(2, 300.0, 240.0), _mf(3, 300.0, 360.0)])
    assert verdict.selected is False
    assert "波动率" in verdict.reason


def test_selection_rejects_small_spend() -> None:
    verdict = _select([_mf(1, 100.0, 60.0), _mf(2, 100.0, 60.0), _mf(3, 100.0, 60.0)])
    assert verdict.selected is False
    assert "日均消耗" in verdict.reason


def test_selection_skips_non_follow_up_stage() -> None:
    verdict = _select(
        [_mf(1, 300.0, 180.0), _mf(2, 300.0, 180.0), _mf(3, 300.0, 180.0)],
        stage=Stage.MATERIAL_OBSERVING,
    )
    assert verdict.selected is False
    assert "不产跟投信号" in verdict.reason
