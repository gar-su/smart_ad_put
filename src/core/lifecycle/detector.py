"""
生命周期判定引擎

基于数据分析验证的阈值:
- 数据集 0301-0307: 1944个商品, 109198个campaign
- 数据集 0315-0321: 2447个商品, 119392个campaign

参考: src/core/lifecycle/VALIDATION_REPORT.md
"""

from datetime import datetime
from typing import Protocol, TypeVar, Generic

from .stages import Dimension, Stage, LifecycleRecord


T = TypeVar('T')


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
# 数据验证的阈值配置
# =============================================================================

class ProductThresholds:
    """
    商品（短剧）生命周期阈值

    核心发现:
    - 首日消耗 >= 500元: 冷启动率 < 5%
    - 首日消耗 < 50元: 冷启动率 ~32%
    - 衰退率 ~65-70%，是常态
    - CTR 2-3% 是最佳区间
    """

    # 冷启动期
    COLD_START_DURATION_HOURS: int = 24
    COST_CRITICAL: float = 50       # < 50元 冷启动率高 (32%)
    COST_HEALTHY: float = 500       # >= 500元 冷启动率 < 5%
    COST_FIRST_24H_THRESHOLD: float = 100  # 首日投入关键门槛

    # 成长期
    GROWTH_COST_CHANGE_MIN: float = 0.20  # +20% 消耗增长

    # 成熟期
    MATURE_COST_CHANGE_RANGE: tuple = (-0.20, 0.20)  # -20% ~ +20% 消耗稳定
    MATURE_COST_MIN: float = 200  # 最低消耗门槛

    # 衰退期
    DECAY_COST_CHANGE_MAX: float = -0.30  # -30% 消耗下降
    DECAY_CONSECUTIVE_HOURS: int = 3  # 连续3天才判定衰退（防抖动）

    # CTR 最佳区间
    CTR_GOLDEN_RANGE: tuple = (0.02, 0.05)  # 2-5% 是黄金区间
    CTR_HIGH_RISK: float = 0.06  # > 6% 可能有刷量风险


class CampaignThresholds:
    """
    广告单元（Campaign）生命周期阈值

    核心发现:
    - 60%+ 的 campaign 在24h内死亡
    - 首日消耗 >= 200元 存活率更高
    - 成本 < 10元反而存活率高（可能是测试素材）
    """

    # 冷启动期
    COLD_START_DURATION_HOURS: int = 24
    COST_CRITICAL: float = 50   # < 50元 死亡率高
    COST_HEALTHY: float = 200   # >= 200元 存活率更高

    # 稳定投放期
    STABLE_COST_CHANGE_RANGE: tuple = (-0.30, 0.30)

    # 衰退期
    DECAY_COST_DROP_MIN: float = 0.30  # 消耗下降30%+
    DECAY_CONSECUTIVE_HOURS: int = 12  # 连续12小时

    # 关停期
    SHUTDOWN_COST_PER_HOUR_MAX: float = 1.0  # 每小时<1元
    SHUTDOWN_DURATION_MIN: int = 48  # 持续48h以上


class MaterialThresholds:
    """
    素材生命周期阈值

    注意: 当前数据中没有素材ID，此阈值基于行业经验
    """

    FRESH_DAYS: int = 3           # 新鲜期：投放3天内
    GOLDEN_CTR_DROP_MAX: float = 0.20  # 黄金期：CTR下降<20%
    FATIGUE_CTR_DROP_MIN: float = 0.40  # 疲劳期：CTR下降>40%
    FATIGUE_FREQUENCY: int = 50  # 疲劳期：展示频次>50


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
# 商品生命周期检测器
# =============================================================================

class ProductLifecycleDetector:
    """
    商品（短剧）生命周期检测器

    使用数据验证的阈值进行判定
    """

    def __init__(self, thresholds: ProductThresholds | None = None):
        self.t = thresholds or ProductThresholds()

    def detect(
        self,
        duration_hours: float,
        cost_first_24h: float,
        cost_last_24h: float,
        cost_change_pct: float,
        ctr_first_24h: float | None = None,
        total_pays: int = 0,
    ) -> DetectionResult:
        """
        检测商品生命周期阶段

        Args:
            duration_hours: 投放时长（小时）
            cost_first_24h: 首日消耗
            cost_last_24h: 最后24小时消耗
            cost_change_pct: 消耗变化百分比 (如 0.20 = +20%)
            ctr_first_24h: 首日CTR (可选)
            total_pays: 总付费数
        """

        # ========== 冷启动失败 ==========
        if duration_hours <= self.t.COLD_START_DURATION_HOURS:
            if cost_first_24h < self.t.COST_CRITICAL:
                return DetectionResult(
                    stage=Stage.PRODUCT_COLD_START,
                    confidence=0.9,
                    reason=f"冷启动失败: 投放{duration_hours:.0f}h, 首日消耗{cost_first_24h:.1f}元 < {self.t.COST_CRITICAL}元",
                    metrics={
                        "duration_hours": duration_hours,
                        "cost_first_24h": cost_first_24h,
                        "cold_start_rate": 0.32  # 32% 冷启动率
                    }
                )

        # ========== 成长期 ==========
        if cost_change_pct >= self.t.GROWTH_COST_CHANGE_MIN and duration_hours > 24:
            return DetectionResult(
                stage=Stage.PRODUCT_GROWTH,
                confidence=0.85,
                reason=f"成长期: 消耗增长{cost_change_pct*100:.1f}% > {self.t.GROWTH_COST_CHANGE_MIN*100:.0f}%",
                metrics={
                    "cost_change_pct": cost_change_pct,
                    "duration_hours": duration_hours
                }
            )

        # ========== 衰退期 ==========
        if cost_change_pct < self.t.DECAY_COST_CHANGE_MAX:
            return DetectionResult(
                stage=Stage.PRODUCT_DECLINE,
                confidence=0.90,
                reason=f"衰退期: 消耗下降{abs(cost_change_pct)*100:.1f}% < {abs(self.t.DECAY_COST_CHANGE_MAX)*100:.0f}%",
                metrics={
                    "cost_change_pct": cost_change_pct,
                    "total_pays": total_pays
                }
            )

        # ========== 成熟期 ==========
        if (
            self.t.MATURE_COST_CHANGE_RANGE[0] < cost_change_pct < self.t.MATURE_COST_CHANGE_RANGE[1]
            and cost_first_24h >= self.t.MATURE_COST_MIN
        ):
            return DetectionResult(
                stage=Stage.PRODUCT_MATURE,
                confidence=0.80,
                reason=f"成熟期: 消耗稳定({cost_change_pct*100:.1f}%), 首日消耗{cost_first_24h:.1f}元",
                metrics={
                    "cost_change_pct": cost_change_pct,
                    "cost_first_24h": cost_first_24h
                }
            )

        # ========== 引入期（默认）==========
        return DetectionResult(
            stage=Stage.PRODUCT_INTRODUCING,
            confidence=0.60,
            reason=f"引入期: duration={duration_hours:.0f}h, 首日消耗={cost_first_24h:.1f}元",
            metrics={
                "duration_hours": duration_hours,
                "cost_first_24h": cost_first_24h
            }
        )

    def get_survival_probability(self, cost_first_24h: float) -> float:
        """
        根据首日消耗预测存活概率

        基于数据分析:
        - cost < 50: 冷启动率 32% -> 存活率 68%
        - cost >= 500: 冷启动率 < 5% -> 存活率 > 95%
        """
        if cost_first_24h >= 500:
            return 0.95
        elif cost_first_24h >= 200:
            return 0.85
        elif cost_first_24h >= 100:
            return 0.72
        elif cost_first_24h >= 50:
            return 0.68
        else:
            return 0.68  # < 50 和 50-100 差不多


# =============================================================================
# 广告单元（Campaign）生命周期检测器
# =============================================================================

class CampaignLifecycleDetector:
    """
    广告单元（Campaign）生命周期检测器

    核心发现:
    - 60%+ 的 campaign 在24h内死亡
    - 首日消耗 >= 200元 存活率更高
    """

    def __init__(self, thresholds: CampaignThresholds | None = None):
        self.t = thresholds or CampaignThresholds()

    def detect(
        self,
        duration_hours: float,
        cost_first_24h: float,
        cost_last_24h: float,
        cost_change_pct: float,
        cost_per_hour: float | None = None,
        ctr_first_24h: float | None = None,
        total_pays: int = 0,
    ) -> DetectionResult:
        """
        检测广告单元生命周期阶段
        """

        # ========== 冷死亡 ==========
        if duration_hours <= self.t.COLD_START_DURATION_HOURS:
            if cost_first_24h < self.t.COST_CRITICAL:
                return DetectionResult(
                    stage=Stage.CAMPAIGN_COLD_DEAD,
                    confidence=0.95,
                    reason=f"冷死亡: 投放{duration_hours:.0f}h, 首日消耗{cost_first_24h:.1f}元 < {self.t.COST_CRITICAL}元",
                    metrics={
                        "duration_hours": duration_hours,
                        "cost_first_24h": cost_first_24h,
                        "death_rate": 0.70  # 70% 死亡率
                    }
                )

        # ========== 冷启动（存活但短期）==========
        if duration_hours <= self.t.COLD_START_DURATION_HOURS:
            return DetectionResult(
                stage=Stage.CAMPAIGN_COLD_START,
                confidence=0.85,
                reason=f"冷启动: 存活{duration_hours:.0f}h, 首日消耗{cost_first_24h:.1f}元",
                metrics={
                    "duration_hours": duration_hours,
                    "cost_first_24h": cost_first_24h
                }
            )

        # ========== 关停期 ==========
        if (
            cost_per_hour is not None
            and cost_per_hour < self.t.SHUTDOWN_COST_PER_HOUR_MAX
            and duration_hours > self.t.SHUTDOWN_DURATION_MIN
        ):
            return DetectionResult(
                stage=Stage.CAMPAIGN_SHUTDOWN,
                confidence=0.90,
                reason=f"关停期: 每小时消耗{cost_per_hour:.2f}元 < {self.t.SHUTDOWN_COST_PER_HOUR_MAX}元, 持续{duration_hours:.0f}h",
                metrics={
                    "cost_per_hour": cost_per_hour,
                    "duration_hours": duration_hours
                }
            )

        # ========== 衰退期 ==========
        if cost_change_pct < self.t.DECAY_COST_DROP_MIN:
            return DetectionResult(
                stage=Stage.CAMPAIGN_DECAY,
                confidence=0.85,
                reason=f"衰退期: 消耗下降{abs(cost_change_pct)*100:.1f}% < {abs(self.t.DECAY_COST_DROP_MIN)*100:.0f}%",
                metrics={
                    "cost_change_pct": cost_change_pct
                }
            )

        # ========== 增长期 ==========
        if cost_change_pct > self.t.GROWTH_COST_CHANGE_MIN if hasattr(self.t, 'GROWTH_COST_CHANGE_MIN') else cost_change_pct > 0.20:
            return DetectionResult(
                stage=Stage.CAMPAIGN_GROWTH,
                confidence=0.80,
                reason=f"增长期: 消耗增长{cost_change_pct*100:.1f}%",
                metrics={
                    "cost_change_pct": cost_change_pct
                }
            )

        # ========== 稳定投放期（默认）==========
        return DetectionResult(
            stage=Stage.CAMPAIGN_STABLE,
            confidence=0.75,
            reason=f"稳定期: 消耗变化{cost_change_pct*100:.1f}%, 持续{duration_hours:.0f}h",
            metrics={
                "cost_change_pct": cost_change_pct,
                "duration_hours": duration_hours,
                "total_pays": total_pays
            }
        )

    def get_survival_probability(self, cost_first_24h: float) -> float:
        """
        根据首日消耗预测存活概率
        """
        if cost_first_24h >= 200:
            return 0.85
        elif cost_first_24h >= 100:
            return 0.72
        elif cost_first_24h >= 50:
            return 0.73
        elif cost_first_24h >= 10:
            return 0.27
        else:
            return 0.37  # 极低预算反而略高（可能是测试素材）


# =============================================================================
# 素材生命周期检测器
# =============================================================================

class MaterialLifecycleDetector:
    """
    素材生命周期检测器

    注意: 当前数据中没有素材ID，此检测器基于行业经验设计
    """

    def __init__(self, thresholds: MaterialThresholds | None = None):
        self.t = thresholds or MaterialThresholds()

    def detect(
        self,
        days_since_launch: int,
        ctr_drop_rate: float,
        impression_frequency: int,
        ctr: float | None = None,
    ) -> DetectionResult:
        """
        检测素材生命周期阶段
        """

        # ========== 淘汰期 ==========
        if ctr_drop_rate > self.t.FATIGUE_CTR_DROP_MIN or impression_frequency > self.t.FATIGUE_FREQUENCY:
            return DetectionResult(
                stage=Stage.MATERIAL_ELIMINATED,
                confidence=0.90,
                reason=f"淘汰期: CTR下降{ctr_drop_rate*100:.1f}% 或频次{impression_frequency} > {self.t.FATIGUE_FREQUENCY}",
                metrics={
                    "ctr_drop_rate": ctr_drop_rate,
                    "impression_frequency": impression_frequency
                }
            )

        # ========== 疲劳期 ==========
        if ctr_drop_rate > self.t.GOLDEN_CTR_DROP_MAX:
            return DetectionResult(
                stage=Stage.MATERIAL_FATIGUE,
                confidence=0.80,
                reason=f"疲劳期: CTR下降{ctr_drop_rate*100:.1f}% > {self.t.GOLDEN_CTR_DROP_MAX*100:.0f}%",
                metrics={
                    "ctr_drop_rate": ctr_drop_rate
                }
            )

        # ========== 黄金期 ==========
        if ctr_drop_rate <= self.t.GOLDEN_CTR_DROP_MAX:
            if ctr is not None and self.t.CTR_GOLDEN_RANGE[0] <= ctr <= self.t.CTR_GOLDEN_RANGE[1]:
                return DetectionResult(
                    stage=Stage.MATERIAL_GOLDEN,
                    confidence=0.85,
                    reason=f"黄金期: CTR {ctr*100:.1f}%, 下降{ctr_drop_rate*100:.1f}%",
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

    async def detect_product(
        self,
        product_id: str,
        duration_hours: float,
        cost_first_24h: float,
        cost_last_24h: float,
        cost_change_pct: float,
        ctr_first_24h: float | None = None,
        total_pays: int = 0,
    ) -> LifecycleRecord:
        """检测商品生命周期"""
        result = self.product_detector.detect(
            duration_hours=duration_hours,
            cost_first_24h=cost_first_24h,
            cost_last_24h=cost_last_24h,
            cost_change_pct=cost_change_pct,
            ctr_first_24h=ctr_first_24h,
            total_pays=total_pays,
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

    async def detect_campaign(
        self,
        campaign_id: str,
        duration_hours: float,
        cost_first_24h: float,
        cost_last_24h: float,
        cost_change_pct: float,
        cost_per_hour: float | None = None,
        ctr_first_24h: float | None = None,
        total_pays: int = 0,
    ) -> LifecycleRecord:
        """检测广告单元（campaign）生命周期"""
        result = self.campaign_detector.detect(
            duration_hours=duration_hours,
            cost_first_24h=cost_first_24h,
            cost_last_24h=cost_last_24h,
            cost_change_pct=cost_change_pct,
            cost_per_hour=cost_per_hour,
            ctr_first_24h=ctr_first_24h,
            total_pays=total_pays,
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
