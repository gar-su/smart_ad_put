"""原子事实聚合测试

服务只收原始原子事实（钱/量/身份），ROI 等派生指标在聚合层算
（数据契约 docs/data_contract.md §1、§7）。
"""

from datetime import date, timedelta

import pytest

from src.core.lifecycle.aggregation import (
    DailyFact,
    FactValidationError,
    HourlyFact,
    aggregate_campaign,
    aggregate_product,
)

D0 = date(2026, 4, 23)


def _daily(d: date, spend: float, order: float, ad: float) -> DailyFact:
    return DailyFact(date=d, spend=spend, income_order=order, income_ad=ad)


def _hourly(d: date, hour: int, spend: float, order: float, ad: float) -> HourlyFact:
    return HourlyFact(date=d, hour=hour, spend=spend, income_order=order, income_ad=ad)


# ============================================================
# product：日级原子事实
# ============================================================


def test_product_single_day():
    m = aggregate_product([_daily(D0, 1000.0, 400.0, 100.0)])
    assert m.total_cost == 1000.0
    assert m.total_revenue == 500.0
    assert m.order_amt == 400.0
    assert m.ad_amt == 100.0
    assert m.duration_hours == 24.0
    assert m.recent_roi_history == [0.5]


def test_product_multi_day_sums_and_roi_oldest_first():
    m = aggregate_product(
        [
            _daily(D0, 100.0, 40.0, 10.0),  # roi 0.5
            _daily(date(2026, 4, 24), 200.0, 40.0, 20.0),  # roi 0.3
            _daily(date(2026, 4, 25), 300.0, 30.0, 30.0),  # roi 0.2
        ]
    )
    assert m.total_cost == 600.0
    assert m.total_revenue == 170.0
    assert m.order_amt == 110.0
    assert m.ad_amt == 60.0
    assert m.duration_hours == 72.0
    assert m.recent_roi_history == [0.5, 0.3, 0.2]


def test_product_unsorted_input_sorted_by_date():
    facts = [
        _daily(date(2026, 4, 25), 300.0, 30.0, 30.0),
        _daily(D0, 100.0, 40.0, 10.0),
        _daily(date(2026, 4, 24), 200.0, 40.0, 20.0),
    ]
    m = aggregate_product(facts)
    assert m.recent_roi_history == [0.5, 0.3, 0.2]


def test_product_zero_spend_day_roi_is_zero():
    m = aggregate_product([_daily(D0, 0.0, 0.0, 0.0), _daily(date(2026, 4, 24), 100.0, 50.0, 0.0)])
    assert m.recent_roi_history == [0.0, 0.5]


def test_product_empty_raises():
    with pytest.raises(FactValidationError, match="为空"):
        aggregate_product([])


def test_product_date_gap_raises():
    with pytest.raises(FactValidationError, match="断档"):
        aggregate_product([_daily(D0, 100.0, 40.0, 10.0), _daily(date(2026, 4, 25), 100.0, 40.0, 10.0)])


# ============================================================
# campaign：小时级原子事实
# ============================================================


def test_campaign_single_hour():
    m = aggregate_campaign([_hourly(D0, 0, 10.0, 4.0, 1.0)])
    assert m.duration_hours == 1.0
    assert m.cost == 10.0
    assert m.revenue == 5.0
    assert m.cost_0_24h == 10.0
    assert m.revenue_0_24h == 5.0
    assert m.cost_24_72h == 0.0
    assert m.cost_72plus == 0.0
    assert m.order_amt == 4.0
    assert m.ad_amt == 1.0


def test_campaign_buckets_by_hour_offset():
    """81 个连续小时：0-24h 共 24 条、24-72h 共 48 条、72h+ 共 9 条"""
    facts = [_hourly(D0 + timedelta(days=o // 24), o % 24, 1.0, 0.5, 0.5) for o in range(81)]
    m = aggregate_campaign(facts)
    assert m.duration_hours == 81.0
    assert m.cost_0_24h == 24.0
    assert m.revenue_0_24h == 24.0
    assert m.cost_24_72h == 48.0
    assert m.revenue_24_72h == 48.0
    assert m.cost_72plus == 9.0
    assert m.revenue_72plus == 9.0
    assert m.cost == 81.0
    assert m.revenue == 81.0


def test_campaign_contiguous_across_midnight():
    facts = [
        _hourly(date(2026, 4, 23), 22, 1.0, 1.0, 0.0),
        _hourly(date(2026, 4, 23), 23, 1.0, 1.0, 0.0),
        _hourly(date(2026, 4, 24), 0, 1.0, 1.0, 0.0),
        _hourly(date(2026, 4, 24), 1, 1.0, 1.0, 0.0),
    ]
    m = aggregate_campaign(facts)
    assert m.duration_hours == 4.0
    assert m.cost_0_24h == 4.0


def test_campaign_hour_gap_raises():
    facts = [
        _hourly(date(2026, 4, 23), 22, 1.0, 1.0, 0.0),
        _hourly(date(2026, 4, 24), 1, 1.0, 1.0, 0.0),
    ]
    with pytest.raises(FactValidationError, match="断档"):
        aggregate_campaign(facts)


def test_campaign_empty_raises():
    with pytest.raises(FactValidationError, match="为空"):
        aggregate_campaign([])
