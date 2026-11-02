"""
生命周期判定引擎

基于数据分析验证的阈值（业务标准: ROI > 40% 为盈利）

核心发现:
- 收入 = d0_order_amt + d0_ad_amt
- ROI = 收入 / 成本
- 盈利标准: ROI > 40%
- 72小时是判断Campaign生死的关键节点
- 前24h ROI < 10% 的Campaign，85%最终无法盈利
- 盈利Campaign的订单收入占比 > 90%
- 6h快速信号: 能盈利的Campaign在6h内ROI即达60%，6h ROI>40%为快速通道

数据集: 0301-0307 和 0315-0321
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol

from .aggregation import MaterialFact, MaterialMetrics, aggregate_material
from .stages import Dimension, LifecycleRecord, Stage


class MetricsProvider(Protocol):
    """指标数据提供者协议"""

    async def get_product_metrics(self, product_id: str) -> dict:
        """获取商品指标"""
        ...

    async def get_material_metrics(self, material_id: str) -> dict:
        """获取素材指标"""
        ...

    async def get_campaign_metrics(self, campaign_id: str) -> dict:
        """获取广告单元（campaign）指标"""
        ...


# =============================================================================
# 基于ROI的阈值配置（业务标准）
# =============================================================================

class ROIThresholds:
    """
    ROI相关的阈值配置

    业务标准: ROI > 40% 为盈利
    """

    # 盈利标准
    PROFITABLE_ROI: float = 0.40  # 40% ROI = 盈利线

    # ROI分段阈值
    ROI_VERY_LOW: float = 0.10    # < 10% = 极低，难以存活
    ROI_LOW: float = 0.20         # < 20% = 低ROI
    ROI_MEDIUM: float = 0.40      # < 40% = 中等ROI

    # 时间节点
    EARLY_SIGNAL_HOURS: int = 6   # 早期信号快速通道（小时）
    COLD_START_HOURS: int = 24    # 冷启动期（小时）
    VERIFY_HOURS: int = 72        # 验证期（小时）
    SUSTAINED_DAYS: int = 7       # 持续盈利判定天数


class CostThresholds:
    """
    成本相关的阈值配置

    注意: 成本本身不是判断标准，需结合ROI
    """

    # 首日成本临界值
    COST_CRITICAL: float = 50      # < 50元 成本极低
    COST_LOW: float = 100          # < 100元 低成本
    COST_MEDIUM: float = 200       # >= 200元 中等成本
    COST_HIGH: float = 500         # >= 500元 高成本


class RevenueThresholds:
    """
    收入相关的阈值配置

    收入 = d0_order_amt + d0_ad_amt
    """

    # 最小收入标准
    REVENUE_ZERO: float = 0       # 无收入
    REVENUE_MINIMAL: float = 1    # 极小收入
    REVENUE_SUSTAINED: float = 10  # 持续收入门槛

    # 收入构成
    ORDER_RATIO_MIN: float = 0.90  # 盈利Campaign订单收入占比 > 90%


# =============================================================================
# 判定结果
# =============================================================================

class DetectionResult:
    """判定结果"""

    def __init__(
        self,
        stage: Stage,
        confidence: float,
        reason: str,
        metrics: dict | None = None
    ):
        self.stage = stage
        self.confidence = confidence  # 0.0 ~ 1.0
        self.reason = reason
        self.metrics = metrics or {}


# =============================================================================
# Campaign 生命周期检测器（基于ROI）
# =============================================================================

class CampaignLifecycleDetector:
    """
    广告单元（Campaign）生命周期检测器

    互斥分段判定（按时长锁段，段内按ROI判定）:

    SEGMENT 0 (< 24h):
      >= 6h, ROI > 40%       → CAMPAIGN_GROWTH (快速通道, conf 0.85)
      其他                     → CAMPAIGN_OBSERVING

    SEGMENT 1 (24-72h):
      roi_0_24h < 10%        → CAMPAIGN_COLD_START
      roi_total 10%-40%      → CAMPAIGN_VERIFY
      roi_total > 40%        → CAMPAIGN_GROWTH (early)

    SEGMENT 2 (> 72h):
      revenue = 0            → CAMPAIGN_COLD_DEAD
      roi_total < 10%        → CAMPAIGN_SHUTDOWN
      peak > 40%, drop >50%  → CAMPAIGN_DECLINE
      >7d, roi > 40% stable  → CAMPAIGN_SUSTAINED
      roi_total > 40%        → CAMPAIGN_GROWTH
      roi 10-40%, trend up   → CAMPAIGN_GROWTH (low conf)
      roi 10-40%, trend down → CAMPAIGN_DECLINE (low conf)
      10-40%, flat           → CAMPAIGN_OBSERVING
    """

    def __init__(
        self,
        roi_thresholds: ROIThresholds | None = None,
        cost_thresholds: CostThresholds | None = None,
        revenue_thresholds: RevenueThresholds | None = None
    ):
        self.roi = roi_thresholds or ROIThresholds()
        self.cost = cost_thresholds or CostThresholds()
        self.revenue = revenue_thresholds or RevenueThresholds()

    def detect(
        self,
        duration_hours: float,
        revenue: float,
        cost: float,
        revenue_0_24h: float = 0,
        cost_0_24h: float = 0,
        revenue_24_72h: float = 0,
        cost_24_72h: float = 0,
        revenue_72plus: float = 0,
        cost_72plus: float = 0,
        order_amt: float = 0,
        ad_amt: float = 0,
    ) -> DetectionResult:
        """
        检测广告单元生命周期阶段（互斥分段判定）

        SEGMENT 0 (< 24h):  OBSERVING | GROWTH (快速通道: >= 6h + ROI > 40%)
        SEGMENT 1 (24-72h): COLD_START | VERIFY | early GROWTH
        SEGMENT 2 (> 72h):  COLD_DEAD | SHUTDOWN | DECLINE | GROWTH | SUSTAINED
        """

        roi_0_24h = revenue_0_24h / cost_0_24h if cost_0_24h > 0 else 0
        roi_24_72h = revenue_24_72h / cost_24_72h if cost_24_72h > 0 else 0
        roi_72plus = revenue_72plus / cost_72plus if cost_72plus > 0 else 0
        roi_total = revenue / cost if cost > 0 else 0
        peak_roi = max(roi_0_24h, roi_24_72h, roi_72plus)

        # ================================================================
        # SEGMENT 0: < 24h — 待观察 / 快速通道
        # ================================================================
        if duration_hours < 24:
            # 快速通道: >= 6h 且 ROI > 40% — 早期盈利信号
            if duration_hours >= self.roi.EARLY_SIGNAL_HOURS and roi_total > self.roi.PROFITABLE_ROI:
                return DetectionResult(
                    stage=Stage.CAMPAIGN_GROWTH,
                    confidence=0.85,
                    reason=f"快速通道: 投放{duration_hours:.0f}h，ROI={roi_total*100:.1f}% > 40%，早期盈利信号",
                    metrics={"roi": roi_total, "duration_hours": duration_hours, "profitability": "early_signal"},
                )
            return DetectionResult(
                stage=Stage.CAMPAIGN_OBSERVING,
                confidence=0.50,
                reason=f"待观察: 投放{duration_hours:.0f}h < 24h，时间不足无法判断",
                metrics={"duration_hours": duration_hours, "revenue": revenue, "roi": roi_total},
            )

        # ================================================================
        # SEGMENT 1: 24-72h — 冷启动 / 验证期 / 早期盈利
        # ================================================================
        if duration_hours <= 72:
            # 冷启动: 前24h ROI < 10%
            if roi_0_24h < self.roi.ROI_VERY_LOW:
                return DetectionResult(
                    stage=Stage.CAMPAIGN_COLD_START,
                    confidence=0.85,
                    reason=f"冷启动: 前24h ROI={roi_0_24h*100:.1f}% < 10%，风险高",
                    metrics={
                        "roi_0_24h": roi_0_24h,
                        "revenue_0_24h": revenue_0_24h,
                        "cost_0_24h": cost_0_24h,
                        "failure_probability": 0.85,
                    },
                )

            # 验证期: ROI在10%-40%之间
            if roi_total <= self.roi.PROFITABLE_ROI:
                return DetectionResult(
                    stage=Stage.CAMPAIGN_VERIFY,
                    confidence=0.75,
                    reason=f"验证期: ROI={roi_total*100:.1f}% (10%-40%)，关键决策点",
                    metrics={"roi": roi_total, "duration_hours": duration_hours, "pass_probability": 0.30},
                )

            # 早期盈利: 24-72h内 ROI > 40%（少见但存在，置信度偏低待验证）
            return DetectionResult(
                stage=Stage.CAMPAIGN_GROWTH,
                confidence=0.70,
                reason=f"早期成长期: ROI={roi_total*100:.1f}% > 40%，需持续观察",
                metrics={"roi": roi_total, "duration_hours": duration_hours, "profitability": "early"},
            )

        # ================================================================
        # SEGMENT 2: > 72h — 冷死亡 / 关停 / 衰退 / 成长 / 持续盈利
        # ================================================================

        # 冷死亡: 从未产生收入
        if revenue == 0:
            return DetectionResult(
                stage=Stage.CAMPAIGN_COLD_DEAD,
                confidence=0.95,
                reason=f"冷死亡: 投放{duration_hours:.0f}h，从未产生收入",
                metrics={"revenue": 0, "cost": cost, "duration_hours": duration_hours, "death_probability": 0.95},
            )

        # 关停期: ROI < 10%
        if roi_total < self.roi.ROI_VERY_LOW:
            return DetectionResult(
                stage=Stage.CAMPAIGN_SHUTDOWN,
                confidence=0.90,
                reason=f"关停期: ROI={roi_total*100:.1f}% < 10%，持续{duration_hours:.0f}h",
                metrics={"roi": roi_total, "duration_hours": duration_hours, "survival_probability": 0.05},
            )

        # 衰退期: ROI从高点下降 > 50%
        if peak_roi > self.roi.PROFITABLE_ROI and roi_total < peak_roi * 0.5:
            decline_pct = (peak_roi - roi_total) / peak_roi if peak_roi > 0 else 0
            return DetectionResult(
                stage=Stage.CAMPAIGN_DECLINE,
                confidence=0.85,
                reason=f"衰退期: ROI从{peak_roi*100:.1f}%下降到{roi_total*100:.1f}%，降幅>{decline_pct*100:.0f}%",
                metrics={"roi_peak": peak_roi, "roi_current": roi_total, "decline_pct": decline_pct},
            )

        # 持续盈利: ROI > 40% 超过7天
        if duration_hours > 168 and roi_total > self.roi.PROFITABLE_ROI and roi_72plus > self.roi.PROFITABLE_ROI:
            return DetectionResult(
                stage=Stage.CAMPAIGN_SUSTAINED,
                confidence=0.90,
                reason=f"持续盈利: ROI={roi_total*100:.1f}% > 40%，持续超过7天",
                metrics={"roi": roi_total, "duration_hours": duration_hours, "profitability": "sustained"},
            )

        # 成长期: ROI > 40%
        if roi_total > self.roi.PROFITABLE_ROI:
            return DetectionResult(
                stage=Stage.CAMPAIGN_GROWTH,
                confidence=0.85,
                reason=f"成长期: ROI={roi_total*100:.1f}% > 40%，进入盈利阶段",
                metrics={"roi": roi_total, "duration_hours": duration_hours, "profitability": "profitable"},
            )

        # >72h 但 ROI 在 10-40% 之间: 根据趋势归类
        if roi_72plus > roi_0_24h * 1.5:
            return DetectionResult(
                stage=Stage.CAMPAIGN_GROWTH,
                confidence=0.60,
                reason=f"趋势向好: ROI={roi_total*100:.1f}%，后期ROI提升显著",
                metrics={"roi": roi_total, "roi_72plus": roi_72plus, "roi_0_24h": roi_0_24h},
            )
        if roi_72plus < roi_0_24h * 0.5 and roi_72plus > 0:
            return DetectionResult(
                stage=Stage.CAMPAIGN_DECLINE,
                confidence=0.60,
                reason=f"趋势下滑: ROI={roi_total*100:.1f}%，后期表现持续走弱",
                metrics={"roi": roi_total, "roi_72plus": roi_72plus, "roi_0_24h": roi_0_24h},
            )

        return DetectionResult(
            stage=Stage.CAMPAIGN_OBSERVING,
            confidence=0.50,
            reason=f"待观察: ROI={roi_total*100:.1f}% (10-40%)，趋势不明，需持续监测",
            metrics={"roi": roi_total, "duration_hours": duration_hours},
        )

    def get_profitability_probability(self, roi_0_24h: float, roi_72h: float | None = None) -> float:
        """
        根据早期ROI预测盈利概率

        基于数据分析:
        - 前24h ROI < 10%: 85%最终不盈利
        - 72h后 ROI > 40%: 92%最终盈利
        """
        if roi_0_24h > self.roi.PROFITABLE_ROI:
            return 0.90  # 早期盈利，高置信度
        elif roi_0_24h > self.roi.ROI_MEDIUM:
            return 0.70
        elif roi_0_24h > self.roi.ROI_VERY_LOW:
            return 0.30
        else:
            return 0.15  # 早期ROI极低


# =============================================================================
# 商品（ShortPlay）生命周期检测器
# =============================================================================

class ProductLifecycleDetector:
    """
    商品（短剧）生命周期检测器

    商品维度关注整体盈利能力和持续时间
    """

    def __init__(
        self,
        roi_thresholds: ROIThresholds | None = None,
        cost_thresholds: CostThresholds | None = None
    ):
        self.roi = roi_thresholds or ROIThresholds()
        self.cost = cost_thresholds or CostThresholds()

    def detect(
        self,
        total_revenue: float,
        total_cost: float,
        campaign_count: int,
        duration_hours: float,
        order_amt: float = 0,
        ad_amt: float = 0,
        recent_roi_history: list[float] | None = None,
    ) -> DetectionResult:
        """
        检测商品生命周期阶段

        基于时间段 + ROI指标:
        - < 3天: OBSERVING
        - 3-7天: VALIDATING (ROI > 40% → ENTRY, ROI < 10% → EXIT)
        - 7-14天: CONFIRMING (趋势确认)
        - > 14天: SUSTAINED/DECLINE

        Args:
            total_revenue: 总收入
            total_cost: 总成本
            campaign_count: 关联的Campaign数量
            duration_hours: 最大投放时长
            order_amt: 订单收入
            ad_amt: 广告收入
            recent_roi_history: 近N天的每日ROI（oldest-first，最早在前）
        """
        recent_roi_history = recent_roi_history or []

        roi = total_revenue / total_cost if total_cost > 0 else 0
        days = duration_hours / 24  # 转换为天数

        # ========== < 3天: OBSERVING ==========
        if days < 3:
            return DetectionResult(
                stage=Stage.PRODUCT_OBSERVING,
                confidence=0.50,
                reason=f"待观察: 投放{days:.0f}天 < 3天，时间不足",
                metrics={"duration_hours": duration_hours, "roi": roi}
            )

        # ========== 3-7天: VALIDATING ==========
        if 3 <= days < 7:
            if len(recent_roi_history) >= 3:
                recent_3_avg = sum(recent_roi_history[-3:]) / 3
                if recent_3_avg > 0.40:
                    return DetectionResult(
                        stage=Stage.PRODUCT_ENTRY,
                        confidence=0.87,
                        reason=f"入场期: 近3天ROI均值={recent_3_avg*100:.1f}% > 40%",
                        metrics={"roi": roi, "recent_3_avg": recent_3_avg}
                    )
                if recent_3_avg < 0.10:
                    return DetectionResult(
                        stage=Stage.PRODUCT_EXIT,
                        confidence=0.85,
                        reason=f"退出期: ROI={recent_3_avg*100:.1f}% < 10%",
                        metrics={"roi": roi, "recent_3_avg": recent_3_avg}
                    )
            return DetectionResult(
                stage=Stage.PRODUCT_OBSERVING,
                confidence=0.60,
                reason=f"验证中: ROI={roi*100:.1f}%，等待更多信息",
                metrics={"roi": roi}
            )

        # ========== 7-14天: CONFIRMING ==========
        if 7 <= days < 14:
            return self._detect_confirming_phase(recent_roi_history, roi)

        # ========== > 14天: SUSTAINED/DECLINE ==========
        if days >= 14:
            return self._detect_sustained_phase(recent_roi_history, roi)

        # ========== 默认 ==========
        return DetectionResult(
            stage=Stage.PRODUCT_OBSERVING,
            confidence=0.50,
            reason=f"观察中: ROI={roi*100:.1f}%",
            metrics={"roi": roi}
        )

    def _detect_confirming_phase(self, recent_roi_history: list[float], roi: float) -> DetectionResult:
        """7-14天确认阶段"""
        # EXIT: ROI < 10%
        if len(recent_roi_history) >= 3:
            recent_3_avg = sum(recent_roi_history[-3:]) / 3
            if recent_3_avg < 0.10:
                return DetectionResult(
                    stage=Stage.PRODUCT_EXIT,
                    confidence=0.85,
                    reason=f"退出期: ROI={recent_3_avg*100:.1f}% < 10%",
                    metrics={"roi": roi}
                )

        # DECLINE: ROI 下滑 > 30%  (优先于 SUSTAINED)
        if len(recent_roi_history) >= 5:
            mid = len(recent_roi_history) // 2
            first_half = recent_roi_history[:mid]
            second_half = recent_roi_history[mid:]
            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                if first_avg > 0 and (first_avg - second_avg) / first_avg > 0.30:
                    return DetectionResult(
                        stage=Stage.PRODUCT_DECLINE,
                        confidence=0.80,
                        reason=f"衰退期: ROI下降{((first_avg-second_avg)/first_avg)*100:.1f}% > 30%",
                        metrics={"roi": roi, "first_half_avg": first_avg, "second_half_avg": second_avg}
                    )

        # GROWTH: ROI > 40% + 趋势上升 > 20%
        if len(recent_roi_history) >= 6:
            recent_3_avg = sum(recent_roi_history[-3:]) / 3
            previous_3_avg = sum(recent_roi_history[-6:-3]) / 3
            if recent_3_avg > 0.40 and previous_3_avg > 0 and recent_3_avg > previous_3_avg * 1.2:
                return DetectionResult(
                    stage=Stage.PRODUCT_GROWTH,
                    confidence=0.87,
                    reason=f"成长期: ROI>{recent_3_avg*100:.1f}% 且趋势上升{((recent_3_avg/previous_3_avg)-1)*100:.0f}%",
                    metrics={"roi": roi, "recent_3_avg": recent_3_avg, "previous_3_avg": previous_3_avg}
                )

        # SUSTAINED: ROI > 40% 但趋势平稳
        if len(recent_roi_history) >= 3:
            recent_3_avg = sum(recent_roi_history[-3:]) / 3
            if recent_3_avg > 0.40:
                return DetectionResult(
                    stage=Stage.PRODUCT_SUSTAINED,
                    confidence=0.86,
                    reason=f"稳定期: ROI={recent_3_avg*100:.1f}% > 40%，趋势平稳",
                    metrics={"roi": roi, "recent_3_avg": recent_3_avg}
                )

        return DetectionResult(
            stage=Stage.PRODUCT_OBSERVING,
            confidence=0.60,
            reason=f"确认中: ROI={roi*100:.1f}%",
            metrics={"roi": roi}
        )

    def _detect_sustained_phase(self, recent_roi_history: list[float], roi: float) -> DetectionResult:
        """>14天稳定/衰退阶段"""
        # EXIT: ROI < 10% 持续 5天
        if len(recent_roi_history) >= 5 and all(r < 0.10 for r in recent_roi_history[-5:]):
            return DetectionResult(
                stage=Stage.PRODUCT_EXIT,
                confidence=0.85,
                reason="退出期: ROI < 10% 持续5天",
                metrics={"roi": roi}
            )

        # DECLINE: ROI 下滑 > 30%
        if len(recent_roi_history) >= 5:
            mid = len(recent_roi_history) // 2
            first_half = recent_roi_history[:mid]
            second_half = recent_roi_history[mid:]
            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                if first_avg > 0 and (first_avg - second_avg) / first_avg > 0.30:
                    return DetectionResult(
                        stage=Stage.PRODUCT_DECLINE,
                        confidence=0.80,
                        reason=f"衰退期: ROI下降{((first_avg-second_avg)/first_avg)*100:.1f}% > 30%",
                        metrics={"roi": roi}
                    )

        # GROWTH: ROI > 40% + 趋势上升
        if len(recent_roi_history) >= 6:
            recent_3_avg = sum(recent_roi_history[-3:]) / 3
            previous_3_avg = sum(recent_roi_history[-6:-3]) / 3
            if recent_3_avg > 0.40 and previous_3_avg > 0 and recent_3_avg > previous_3_avg * 1.2:
                return DetectionResult(
                    stage=Stage.PRODUCT_GROWTH,
                    confidence=0.87,
                    reason=f"成长期: ROI>{recent_3_avg*100:.1f}% 且趋势上升",
                    metrics={"roi": roi}
                )

        # SUSTAINED: ROI 30-80% 波动
        if len(recent_roi_history) >= 5:
            recent_5 = recent_roi_history[-5:]
            recent_3_avg = sum(recent_roi_history[-3:]) / 3
            if 0.30 <= recent_3_avg <= 0.80 and all(0.30 <= r <= 0.80 for r in recent_5):
                return DetectionResult(
                    stage=Stage.PRODUCT_SUSTAINED,
                    confidence=0.86,
                    reason=f"稳定期: ROI={recent_3_avg*100:.1f}% 在30-80%波动",
                    metrics={"roi": roi}
                )

        # ENTRY: ROI > 40% 但不满足GROWTH条件
        if len(recent_roi_history) >= 3:
            recent_3_avg = sum(recent_roi_history[-3:]) / 3
            if recent_3_avg > 0.40:
                return DetectionResult(
                    stage=Stage.PRODUCT_ENTRY,
                    confidence=0.87,
                    reason=f"入场期: ROI={recent_3_avg*100:.1f}% > 40%",
                    metrics={"roi": roi}
                )

        return DetectionResult(
            stage=Stage.PRODUCT_OBSERVING,
            confidence=0.50,
            reason=f"观察中: ROI={roi*100:.1f}%",
            metrics={"roi": roi}
        )


# =============================================================================
# 素材生命周期检测器
# =============================================================================

class MaterialThresholds:
    """素材维度阈值（基于素材日级数据回测标定）"""

    RECENT_2D_ROI_MIN: float = 0.30         # 稳定期要求近2日 ROI 均值
    RECENT_2D_COST_RATIO_MIN: float = 0.50  # 近2日消耗占比，低于此视为放量停滞
    ROI_DROP_FROM_PEAK: float = 0.50        # 较峰值 ROI 降幅
    CTR_DROP: float = 0.20                  # 近2日 CTR 较前3日降幅

    # 选品闸门（A 方案：精确率 73%，约 5.6 条/天）
    MIN_TOTAL_ROI: float = 0.50             # 累计 ROI 必须高于盈利线才有选品余量
    MAX_ROI_CV: float = 0.50                # 单日 ROI 波动率上限，过滤一日冲高
    MIN_AVG_DAILY_COST: float = 200.0       # 日均消耗下限，相当于“已被系统放量验证”


@dataclass(frozen=True)
class MaterialSelectionVerdict:
    """素材选品结果（生命周期阶段之上的跟投闸门）"""

    selected: bool
    reason: str


class MaterialLifecycleDetector:
    """
    素材生命周期检测器（互斥分段判定）

    SEGMENT 0 (< 3 个活跃日):
      其他                                     → MATERIAL_OBSERVING

    SEGMENT 1 (3-4 个活跃日):
      近3日ROI < 10%                           → MATERIAL_ELIMINATED
      近3日ROI > 40% 且 近2日消耗占比 >= 50%    → MATERIAL_ENTRY
      其他                                     → MATERIAL_OBSERVING

    SEGMENT 2 (>= 5 个活跃日):
      近3日ROI < 10%                           → MATERIAL_ELIMINATED
      曾达标 且 (ROI较峰值降>50% 或 CTR较前3日降>20%) → MATERIAL_FATIGUE
      近3日ROI > 40% 且 近2日ROI均值>=30% 且 近2日消耗占比>=50% → MATERIAL_SUSTAINED
      其他                                     → MATERIAL_OBSERVING
    """

    def __init__(
        self,
        roi_thresholds: ROIThresholds | None = None,
        material_thresholds: MaterialThresholds | None = None,
    ):
        self.roi = roi_thresholds or ROIThresholds()
        self.material = material_thresholds or MaterialThresholds()

    def detect(self, metrics: MaterialMetrics) -> DetectionResult:
        """检测素材生命周期阶段（输入为聚合后的活跃日指标）"""

        # ================================================================
        # SEGMENT 0: < 3 个活跃日 — 时间不足
        # ================================================================
        if metrics.active_days < 3:
            return DetectionResult(
                stage=Stage.MATERIAL_OBSERVING,
                confidence=0.50,
                reason=f"待观察: 活跃投放{metrics.active_days}天 < 3天，时间不足",
                metrics={"active_days": metrics.active_days, "roi": metrics.recent_3d_roi},
            )

        # ================================================================
        # SEGMENT 1: 3-4 个活跃日 — 入场判定
        # ================================================================
        if metrics.active_days < 5:
            if metrics.recent_3d_roi < self.roi.ROI_VERY_LOW:
                return DetectionResult(
                    stage=Stage.MATERIAL_ELIMINATED,
                    confidence=0.85,
                    reason=f"淘汰期: 近3日ROI={metrics.recent_3d_roi * 100:.1f}% < 10%",
                    metrics={"active_days": metrics.active_days, "recent_3d_roi": metrics.recent_3d_roi},
                )
            if (
                metrics.recent_3d_roi > self.roi.PROFITABLE_ROI
                and metrics.recent_2d_cost_ratio >= self.material.RECENT_2D_COST_RATIO_MIN
            ):
                return DetectionResult(
                    stage=Stage.MATERIAL_ENTRY,
                    confidence=0.80,
                    reason=(
                        f"入场期: 近3日ROI={metrics.recent_3d_roi * 100:.1f}% > 40%，"
                        f"近2日消耗占比{metrics.recent_2d_cost_ratio * 100:.0f}%"
                    ),
                    metrics={
                        "active_days": metrics.active_days,
                        "recent_3d_roi": metrics.recent_3d_roi,
                        "recent_2d_cost_ratio": metrics.recent_2d_cost_ratio,
                    },
                )
            return DetectionResult(
                stage=Stage.MATERIAL_OBSERVING,
                confidence=0.50,
                reason=f"待观察: 近3日ROI={metrics.recent_3d_roi * 100:.1f}%，未过盈利线或消耗萎缩",
                metrics={"active_days": metrics.active_days, "recent_3d_roi": metrics.recent_3d_roi},
            )

        # ================================================================
        # SEGMENT 2: >= 5 个活跃日 — 持续 / 疲劳 / 淘汰
        # ================================================================

        # 淘汰: 近3日 ROI < 10%
        if metrics.recent_3d_roi < self.roi.ROI_VERY_LOW:
            return DetectionResult(
                stage=Stage.MATERIAL_ELIMINATED,
                confidence=0.85,
                reason=f"淘汰期: 近3日ROI={metrics.recent_3d_roi * 100:.1f}% < 10%",
                metrics={"active_days": metrics.active_days, "recent_3d_roi": metrics.recent_3d_roi},
            )

        roi_fatigue = (
            metrics.peak_daily_roi >= self.roi.PROFITABLE_ROI
            and metrics.recent_2d_roi_avg
            < metrics.peak_daily_roi * (1 - self.material.ROI_DROP_FROM_PEAK)
        )
        ctr_fatigue = (
            metrics.prior_3d_ctr > 0
            and metrics.recent_2d_ctr < metrics.prior_3d_ctr * (1 - self.material.CTR_DROP)
        )
        if roi_fatigue or ctr_fatigue:
            return DetectionResult(
                stage=Stage.MATERIAL_FATIGUE,
                confidence=0.80,
                reason=(
                    f"疲劳期: 峰值ROI={metrics.peak_daily_roi * 100:.1f}%，"
                    f"近2日ROI均值={metrics.recent_2d_roi_avg * 100:.1f}%，"
                    f"CTR {metrics.prior_3d_ctr * 100:.2f}% → {metrics.recent_2d_ctr * 100:.2f}%"
                ),
                metrics={
                    "peak_daily_roi": metrics.peak_daily_roi,
                    "recent_2d_roi_avg": metrics.recent_2d_roi_avg,
                    "recent_2d_ctr": metrics.recent_2d_ctr,
                    "prior_3d_ctr": metrics.prior_3d_ctr,
                },
            )

        # 持续: 近3日 ROI > 40% + 近2日 ROI 均值 >= 30% + 消耗未萎缩
        if (
            metrics.recent_3d_roi > self.roi.PROFITABLE_ROI
            and metrics.recent_2d_roi_avg >= self.material.RECENT_2D_ROI_MIN
            and metrics.recent_2d_cost_ratio >= self.material.RECENT_2D_COST_RATIO_MIN
        ):
            return DetectionResult(
                stage=Stage.MATERIAL_SUSTAINED,
                confidence=0.85,
                reason=(
                    f"稳定期: 近3日ROI={metrics.recent_3d_roi * 100:.1f}% > 40%，"
                    f"近2日ROI均值={metrics.recent_2d_roi_avg * 100:.1f}%"
                ),
                metrics={
                    "active_days": metrics.active_days,
                    "recent_3d_roi": metrics.recent_3d_roi,
                    "recent_2d_roi_avg": metrics.recent_2d_roi_avg,
                    "recent_2d_cost_ratio": metrics.recent_2d_cost_ratio,
                },
            )

        return DetectionResult(
            stage=Stage.MATERIAL_OBSERVING,
            confidence=0.50,
            reason=f"待观察: 近3日ROI={metrics.recent_3d_roi * 100:.1f}%，趋势未确认",
            metrics={"active_days": metrics.active_days, "recent_3d_roi": metrics.recent_3d_roi},
        )

    def select(self, stage: Stage, metrics: MaterialMetrics) -> MaterialSelectionVerdict:
        """选品闸门：在生命周期阶段之上判断是否值得新建投放

        只有入场期 / 稳定期进入选品；再要求累计 ROI 有余量、ROI 稳定、日均消耗有规模。
        """
        if stage not in (Stage.MATERIAL_ENTRY, Stage.MATERIAL_SUSTAINED):
            return MaterialSelectionVerdict(False, f"不选择: 阶段 {stage.value} 不产跟投信号")
        if metrics.total_roi <= self.material.MIN_TOTAL_ROI:
            return MaterialSelectionVerdict(
                False,
                f"不选择: 累计ROI={metrics.total_roi * 100:.1f}% ≤ "
                f"{self.material.MIN_TOTAL_ROI * 100:.0f}%",
            )
        if metrics.roi_cv > self.material.MAX_ROI_CV:
            return MaterialSelectionVerdict(
                False,
                f"不选择: ROI波动率={metrics.roi_cv:.2f} > {self.material.MAX_ROI_CV:.2f}",
            )
        if metrics.avg_daily_cost < self.material.MIN_AVG_DAILY_COST:
            return MaterialSelectionVerdict(
                False,
                f"不选择: 日均消耗={metrics.avg_daily_cost:.1f} < "
                f"{self.material.MIN_AVG_DAILY_COST:.0f}",
            )
        return MaterialSelectionVerdict(
            True,
            f"选择通过: 累计ROI={metrics.total_roi * 100:.1f}% > 50%，"
            f"波动率={metrics.roi_cv:.2f} ≤ 0.50，日均消耗={metrics.avg_daily_cost:.1f} ≥ 200",
        )


# =============================================================================
# 统一入口
# =============================================================================

class LifecycleDetector:
    """
    统一生命周期检测器

    支持商品、素材、广告单元三种维度的检测
    """

    def __init__(self, metrics_provider: MetricsProvider | None = None):
        self.metrics = metrics_provider
        self.product_detector = ProductLifecycleDetector()
        self.campaign_detector = CampaignLifecycleDetector()
        self.material_detector = MaterialLifecycleDetector()

    async def detect_campaign(
        self,
        campaign_id: str,
        duration_hours: float,
        revenue: float,
        cost: float,
        revenue_0_24h: float = 0,
        cost_0_24h: float = 0,
        revenue_24_72h: float = 0,
        cost_24_72h: float = 0,
        revenue_72plus: float = 0,
        cost_72plus: float = 0,
        order_amt: float = 0,
        ad_amt: float = 0,
    ) -> LifecycleRecord:
        """检测广告单元生命周期"""
        result = self.campaign_detector.detect(
            duration_hours=duration_hours,
            revenue=revenue,
            cost=cost,
            revenue_0_24h=revenue_0_24h,
            cost_0_24h=cost_0_24h,
            revenue_24_72h=revenue_24_72h,
            cost_24_72h=cost_24_72h,
            revenue_72plus=revenue_72plus,
            cost_72plus=cost_72plus,
            order_amt=order_amt,
            ad_amt=ad_amt,
        )

        return LifecycleRecord(
            dimension=Dimension.CAMPAIGN,
            entity_id=campaign_id,
            current_stage=result.stage,
            stage_entered_at=datetime.utcnow(),
            metrics_snapshot=result.metrics,
            confidence=result.confidence,
            detection_reason=result.reason,
        )

    async def detect_product(
        self,
        product_id: str,
        total_revenue: float,
        total_cost: float,
        campaign_count: int,
        duration_hours: float,
        order_amt: float = 0,
        ad_amt: float = 0,
        recent_roi_history: list[float] | None = None,
    ) -> LifecycleRecord:
        """检测商品生命周期"""
        result = self.product_detector.detect(
            total_revenue=total_revenue,
            total_cost=total_cost,
            campaign_count=campaign_count,
            duration_hours=duration_hours,
            order_amt=order_amt,
            ad_amt=ad_amt,
            recent_roi_history=recent_roi_history,
        )

        return LifecycleRecord(
            dimension=Dimension.PRODUCT,
            entity_id=product_id,
            current_stage=result.stage,
            stage_entered_at=datetime.utcnow(),
            metrics_snapshot=result.metrics,
            confidence=result.confidence,
            detection_reason=result.reason,
        )

    async def detect_material(
        self,
        material_id: str,
        facts: Sequence[MaterialFact],
    ) -> LifecycleRecord:
        """检测素材生命周期（原始日级事实 → 聚合 → 判定 + 选品）"""
        metrics = aggregate_material(facts)
        result = self.material_detector.detect(metrics)
        verdict = self.material_detector.select(result.stage, metrics)
        snapshot = asdict(metrics)
        snapshot["selected"] = verdict.selected
        snapshot["selection_reason"] = verdict.reason

        return LifecycleRecord(
            dimension=Dimension.MATERIAL,
            entity_id=material_id,
            current_stage=result.stage,
            stage_entered_at=datetime.utcnow(),
            metrics_snapshot=snapshot,
            confidence=result.confidence,
            detection_reason=result.reason,
        )
