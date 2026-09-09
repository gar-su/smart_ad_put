"""原子事实 → 判定输入 的聚合

服务只收原始原子事实（钱/量/身份），ROI、分段收入、观测跨度等派生指标
在本层计算（数据契约 docs/data_contract.md §1、§7）。

- product 维度：日级记录 → 累计收入/成本 + 每日 ROI 序列
- campaign 维度：小时级记录 → 0-24h / 24-72h / 72h+ 三段收入与成本
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


class FactValidationError(ValueError):
    """原子事实不满足供给契约（记录为空、时间断档、小时越界）"""


@dataclass(frozen=True)
class DailyFact:
    """短剧视频的一天原子事实"""

    date: date
    spend: float
    income_order: float
    income_ad: float


@dataclass(frozen=True)
class HourlyFact:
    """Campaign 的一小时原子事实"""

    date: date
    hour: int
    spend: float
    income_order: float
    income_ad: float


@dataclass(frozen=True)
class ProductMetrics:
    """product 维度判定输入"""

    total_revenue: float
    total_cost: float
    order_amt: float
    ad_amt: float
    duration_hours: float
    recent_roi_history: list[float]


@dataclass(frozen=True)
class CampaignMetrics:
    """campaign 维度判定输入"""

    duration_hours: float
    revenue: float
    cost: float
    revenue_0_24h: float
    cost_0_24h: float
    revenue_24_72h: float
    cost_24_72h: float
    revenue_72plus: float
    cost_72plus: float
    order_amt: float
    ad_amt: float


def _revenue(fact: DailyFact | HourlyFact) -> float:
    """收入 = 订单收入 + 广告分成（PRD §7.3）"""
    return fact.income_order + fact.income_ad


def _hour_index(fact: HourlyFact) -> int:
    """把 (日期, 小时) 压成绝对小时序号，用于连续性与分段判定"""
    return fact.date.toordinal() * 24 + fact.hour


def aggregate_product(facts: Sequence[DailyFact]) -> ProductMetrics:
    """日级原子事实 → product 判定输入

    观测跨度 = 首条 ~ 末条记录日（含首尾）；每日 ROI 按时间升序排列。
    """
    if not facts:
        raise FactValidationError("records 为空")

    ordered = sorted(facts, key=lambda f: f.date)
    for prev, cur in zip(ordered, ordered[1:]):
        if (cur.date - prev.date).days != 1:
            raise FactValidationError(f"records 日期断档：{prev.date} → {cur.date}")

    order_amt = sum(f.income_order for f in ordered)
    ad_amt = sum(f.income_ad for f in ordered)
    span_days = (ordered[-1].date - ordered[0].date).days + 1

    return ProductMetrics(
        total_revenue=order_amt + ad_amt,
        total_cost=sum(f.spend for f in ordered),
        order_amt=order_amt,
        ad_amt=ad_amt,
        duration_hours=float(span_days * 24),
        recent_roi_history=[(_revenue(f) / f.spend) if f.spend > 0 else 0.0 for f in ordered],
    )


def aggregate_campaign(facts: Sequence[HourlyFact]) -> CampaignMetrics:
    """小时级原子事实 → campaign 判定输入

    分段按距首条记录的小时偏移划分：< 24h、24-72h、≥ 72h。
    """
    if not facts:
        raise FactValidationError("records 为空")

    for f in facts:
        if not 0 <= f.hour <= 23:
            raise FactValidationError(f"records 小时越界：{f.date} hour={f.hour}")

    ordered = sorted(facts, key=_hour_index)
    for prev, cur in zip(ordered, ordered[1:]):
        if _hour_index(cur) - _hour_index(prev) != 1:
            raise FactValidationError(
                f"records 小时断档：{prev.date} {prev.hour}h → {cur.date} {cur.hour}h"
            )

    first = _hour_index(ordered[0])
    # [收入, 成本] × 三段
    seg_0_24 = [0.0, 0.0]
    seg_24_72 = [0.0, 0.0]
    seg_72plus = [0.0, 0.0]
    for f in ordered:
        offset = _hour_index(f) - first
        bucket = seg_0_24 if offset < 24 else seg_24_72 if offset < 72 else seg_72plus
        bucket[0] += _revenue(f)
        bucket[1] += f.spend

    order_amt = sum(f.income_order for f in ordered)
    ad_amt = sum(f.income_ad for f in ordered)

    return CampaignMetrics(
        duration_hours=float(_hour_index(ordered[-1]) - first + 1),
        revenue=order_amt + ad_amt,
        cost=sum(f.spend for f in ordered),
        revenue_0_24h=seg_0_24[0],
        cost_0_24h=seg_0_24[1],
        revenue_24_72h=seg_24_72[0],
        cost_24_72h=seg_24_72[1],
        revenue_72plus=seg_72plus[0],
        cost_72plus=seg_72plus[1],
        order_amt=order_amt,
        ad_amt=ad_amt,
    )
