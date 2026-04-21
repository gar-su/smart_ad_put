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

数据集: 0301-0307 和 0315-0321
"""

from datetime import datetime
from typing import Protocol

from .stages import Dimension, Stage, LifecycleRecord


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
    COLD_START_HOURS: int = 24   # 冷启动期（小时）
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

    基于ROI的判定逻辑:

    阶段判定顺序:
    1. CAMPAIGN_COLD_DEAD: 收入=0 或 ROI始终极低
    2. CAMPAIGN_COLD_START: 前24h ROI < 10%
    3. CAMPAIGN_VERIFY: 24-72h ROI在10-40%区间
    4. CAMPAIGN_GROWTH: 72h后ROI > 40% 且增长
    5. CAMPAIGN_SUSTAINED: ROI > 40% 超过7天
    6. CAMPAIGN_DECLINE: ROI从高点下降 > 50%
    7. CAMPAIGN_SHUTDOWN: ROI < 10% 持续72h+
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
        检测广告单元生命周期阶段

        Args:
            duration_hours: 投放时长（小时）
            revenue: 总收入 (d0_order_amt + d0_ad_amt)
            cost: 总成本
            revenue_0_24h: 前24小时收入
            cost_0_24h: 前24小时成本
            revenue_24_72h: 24-72小时收入
            cost_24_72h: 24-72小时成本
            revenue_72plus: 72小时后收入
            cost_72plus: 72小时后成本
            order_amt: 订单收入
            ad_amt: 广告收入
        """

        # 计算各阶段ROI
        roi_0_24h = revenue_0_24h / cost_0_24h if cost_0_24h > 0 else 0
        roi_24_72h = revenue_24_72h / cost_24_72h if cost_24_72h > 0 else 0
        roi_72plus = revenue_72plus / cost_72plus if cost_72plus > 0 else 0
        roi_total = revenue / cost if cost > 0 else 0

        # ========== 1. 冷死亡: 从未产生收入 ==========
        if revenue == 0:
            return DetectionResult(
                stage=Stage.CAMPAIGN_COLD_DEAD,
                confidence=0.95,
                reason=f"冷死亡: 总收入=0，持续{duration_hours:.0f}h无收入",
                metrics={
                    "revenue": 0,
                    "cost": cost,
                    "duration_hours": duration_hours,
                    "death_probability": 0.95
                }
            )

        # ========== 2. 关停期: ROI < 10% 持续72h+ ==========
        if duration_hours > 72 and roi_total < self.roi.ROI_VERY_LOW:
            return DetectionResult(
                stage=Stage.CAMPAIGN_SHUTDOWN,
                confidence=0.90,
                reason=f"关停期: ROI={roi_total*100:.1f}% < 10%，持续{duration_hours:.0f}h",
                metrics={
                    "roi": roi_total,
                    "duration_hours": duration_hours,
                    "survival_probability": 0.05
                }
            )

        # ========== 3. 冷启动: 前24h ROI < 10% ==========
        if duration_hours <= 24 and roi_0_24h < self.roi.ROI_VERY_LOW:
            return DetectionResult(
                stage=Stage.CAMPAIGN_COLD_START,
                confidence=0.85,
                reason=f"冷启动: 前24h ROI={roi_0_24h*100:.1f}% < 10%，风险高",
                metrics={
                    "roi_0_24h": roi_0_24h,
                    "revenue_0_24h": revenue_0_24h,
                    "cost_0_24h": cost_0_24h,
                    "failure_probability": 0.85
                }
            )

        # ========== 4. 衰退期: ROI从高点下降 > 50% ==========
        if roi_0_24h > self.roi.PROFITABLE_ROI and roi_total < roi_0_24h * 0.5:
            return DetectionResult(
                stage=Stage.CAMPAIGN_DECLINE,
                confidence=0.85,
                reason=f"衰退期: ROI从{roi_0_24h*100:.1f}%下降到{roi_total*100:.1f}%，降幅>50%",
                metrics={
                    "roi_initial": roi_0_24h,
                    "roi_current": roi_total,
                    "decline_pct": (roi_0_24h - roi_total) / roi_0_24h if roi_0_24h > 0 else 0
                }
            )

        # ========== 5. 持续盈利: ROI > 40% 超过7天 ==========
        if duration_hours > 168 and roi_total > self.roi.PROFITABLE_ROI:
            # 检查是否持续保持高ROI
            if roi_72plus > self.roi.PROFITABLE_ROI:
                return DetectionResult(
                    stage=Stage.CAMPAIGN_SUSTAINED,
                    confidence=0.90,
                    reason=f"持续盈利: ROI={roi_total*100:.1f}% > 40%，持续超过7天",
                    metrics={
                        "roi": roi_total,
                        "duration_hours": duration_hours,
                        "profitability": "sustained"
                    }
                )

        # ========== 6. 成长期: 72h后ROI > 40% ==========
        if duration_hours > 72 and roi_total > self.roi.PROFITABLE_ROI:
            return DetectionResult(
                stage=Stage.CAMPAIGN_GROWTH,
                confidence=0.85,
                reason=f"成长期: ROI={roi_total*100:.1f}% > 40%，进入盈利阶段",
                metrics={
                    "roi": roi_total,
                    "duration_hours": duration_hours,
                    "profitability": "profitable"
                }
            )

        # ========== 7. 验证期: 24-72h ROI在10-40% ==========
        if 24 < duration_hours <= 72:
            if self.roi.ROI_VERY_LOW < roi_total <= self.roi.PROFITABLE_ROI:
                return DetectionResult(
                    stage=Stage.CAMPAIGN_VERIFY,
                    confidence=0.75,
                    reason=f"验证期: ROI={roi_total*100:.1f}% (10%-40%)，关键决策点",
                    metrics={
                        "roi": roi_total,
                        "duration_hours": duration_hours,
                        "pass_probability": 0.30
                    }
                )

        # ========== 8. 稳定期（默认）: ROI相对稳定 ==========
        return DetectionResult(
            stage=Stage.CAMPAIGN_VERIFY,  # 归类为验证期
            confidence=0.60,
            reason=f"验证期: ROI={roi_total*100:.1f}%，持续观察中",
            metrics={
                "roi": roi_total,
                "duration_hours": duration_hours
            }
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
    ) -> DetectionResult:
        """
        检测商品生命周期阶段

        Args:
            total_revenue: 总收入
            total_cost: 总成本
            campaign_count: 关联的Campaign数量
            duration_hours: 最大投放时长
            order_amt: 订单收入
            ad_amt: 广告收入
        """

        roi = total_revenue / total_cost if total_cost > 0 else 0
        order_ratio = order_amt / total_revenue if total_revenue > 0 else 0

        # ========== 无收入 ==========
        if total_revenue == 0:
            return DetectionResult(
                stage=Stage.PRODUCT_DEAD,
                confidence=0.95,
                reason=f"无收入商品: 总收入=0，{campaign_count}个Campaign",
                metrics={
                    "total_revenue": 0,
                    "campaign_count": campaign_count
                }
            )

        # ========== 盈利商品 ==========
        if roi > self.roi.PROFITABLE_ROI:
            if duration_hours > 168:
                reason = f"长期盈利商品: ROI={roi*100:.1f}% > 40%，持续{duration_hours:.0f}h"
            else:
                reason = f"盈利商品: ROI={roi*100:.1f}% > 40%"

            return DetectionResult(
                stage=Stage.PRODUCT_PROFITABLE,
                confidence=0.85,
                reason=reason,
                metrics={
                    "roi": roi,
                    "total_revenue": total_revenue,
                    "campaign_count": campaign_count,
                    "order_ratio": order_ratio
                }
            )

        # ========== 亏损商品 ==========
        return DetectionResult(
            stage=Stage.PRODUCT_LOSS,
            confidence=0.80,
            reason=f"亏损商品: ROI={roi*100:.1f}% <= 40%",
            metrics={
                "roi": roi,
                "total_revenue": total_revenue,
                "campaign_count": campaign_count,
                "order_ratio": order_ratio
            }
        )


# =============================================================================
# 素材生命周期检测器
# =============================================================================

class MaterialLifecycleDetector:
    """
    素材生命周期检测器

    注意: 当前数据中没有素材ID，此检测器基于行业经验设计
    """

    def __init__(self):
        pass

    def detect(
        self,
        days_since_launch: int,
        ctr_drop_rate: float,
        impression_frequency: int,
        ctr: float | None = None,
    ) -> DetectionResult:
        """
        检测素材生命周期阶段

        Args:
            days_since_launch: 上线天数
            ctr_drop_rate: CTR下降率
            impression_frequency: 展示频次
            ctr: 当前CTR
        """

        # ========== 淘汰期 ==========
        if ctr_drop_rate > 0.40 or impression_frequency > 50:
            return DetectionResult(
                stage=Stage.MATERIAL_ELIMINATED,
                confidence=0.90,
                reason=f"淘汰期: CTR下降{ctr_drop_rate*100:.1f}% 或频次>{impression_frequency}",
                metrics={
                    "ctr_drop_rate": ctr_drop_rate,
                    "impression_frequency": impression_frequency
                }
            )

        # ========== 疲劳期 ==========
        if ctr_drop_rate > 0.20:
            return DetectionResult(
                stage=Stage.MATERIAL_FATIGUE,
                confidence=0.80,
                reason=f"疲劳期: CTR下降{ctr_drop_rate*100:.1f}% > 20%",
                metrics={
                    "ctr_drop_rate": ctr_drop_rate
                }
            )

        # ========== 黄金期 ==========
        if ctr is not None and 0.02 <= ctr <= 0.05:
            return DetectionResult(
                stage=Stage.MATERIAL_GOLDEN,
                confidence=0.85,
                reason=f"黄金期: CTR {ctr*100:.1f}% (2-5%)",
                metrics={
                    "ctr": ctr,
                    "ctr_drop_rate": ctr_drop_rate
                }
            )

        # ========== 新鲜期（默认）==========
        return DetectionResult(
            stage=Stage.MATERIAL_FRESH,
            confidence=0.70,
            reason=f"新鲜期: 投放{days_since_launch}天",
            metrics={
                "days_since_launch": days_since_launch
            }
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
    ) -> LifecycleRecord:
        """检测商品生命周期"""
        result = self.product_detector.detect(
            total_revenue=total_revenue,
            total_cost=total_cost,
            campaign_count=campaign_count,
            duration_hours=duration_hours,
            order_amt=order_amt,
            ad_amt=ad_amt,
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
