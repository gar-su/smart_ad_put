"""
基建策略引擎

基于生命周期阶段匹配策略，生成基建决策

基于ROI的业务标准:
- 盈利标准: ROI > 40%
- 冷启动失败: 前24h ROI < 10%
- 关键决策点: 72小时
"""

from datetime import datetime, timedelta
from typing import Protocol, TypeVar

from .models import (
    Strategy,
    StrategyMatch,
    Dimension,
    TriggerStage,
    ActionType,
    ScaleConfig,
    Condition,
)
from ..lifecycle.stages import LifecycleRecord, Stage as LifecycleStage


class TriggerStageMapper:
    """生命周期阶段 -> 触发阶段 映射"""

    @staticmethod
    def to_trigger_stage(lifecycle_stage: LifecycleStage) -> TriggerStage:
        """将生命周期阶段映射为触发阶段"""
        mapping = {
            # Campaign维度
            LifecycleStage.CAMPAIGN_OBSERVING: TriggerStage.CAMPAIGN_OBSERVING,
            LifecycleStage.CAMPAIGN_COLD_DEAD: TriggerStage.CAMPAIGN_COLD_DEAD,
            LifecycleStage.CAMPAIGN_COLD_START: TriggerStage.CAMPAIGN_COLD_START,
            LifecycleStage.CAMPAIGN_VERIFY: TriggerStage.CAMPAIGN_VERIFY,
            LifecycleStage.CAMPAIGN_GROWTH: TriggerStage.CAMPAIGN_GROWTH,
            LifecycleStage.CAMPAIGN_SUSTAINED: TriggerStage.CAMPAIGN_SUSTAINED,
            LifecycleStage.CAMPAIGN_DECLINE: TriggerStage.CAMPAIGN_DECLINE,
            LifecycleStage.CAMPAIGN_SHUTDOWN: TriggerStage.CAMPAIGN_SHUTDOWN,
            # Product维度
            LifecycleStage.PRODUCT_OBSERVING: TriggerStage.PRODUCT_OBSERVING,
            LifecycleStage.PRODUCT_ENTRY: TriggerStage.PRODUCT_PROFITABLE,
            LifecycleStage.PRODUCT_GROWTH: TriggerStage.PRODUCT_PROFITABLE,
            LifecycleStage.PRODUCT_SUSTAINED: TriggerStage.PRODUCT_PROFITABLE,
            LifecycleStage.PRODUCT_DECLINE: TriggerStage.PRODUCT_LOSS,
            LifecycleStage.PRODUCT_EXIT: TriggerStage.PRODUCT_LOSS,
            # 素材维度（暂无策略）
            LifecycleStage.MATERIAL_FRESH: TriggerStage.MATERIAL_FRESH,
            LifecycleStage.MATERIAL_GOLDEN: TriggerStage.MATERIAL_GOLDEN,
            LifecycleStage.MATERIAL_FATIGUE: TriggerStage.MATERIAL_FATIGUE,
            LifecycleStage.MATERIAL_ELIMINATED: TriggerStage.MATERIAL_ELIMINATED,
        }
        return mapping.get(lifecycle_stage, TriggerStage.CAMPAIGN_OBSERVING)

    @staticmethod
    def get_dimension(stage: TriggerStage) -> Dimension:
        """获取阶段对应的维度"""
        if stage.value.startswith("campaign_"):
            return Dimension.CAMPAIGN
        elif stage.value.startswith("product_"):
            return Dimension.PRODUCT
        elif stage.value.startswith("material_"):
            return Dimension.CAMPAIGN  # 素材暂无独立维度，归入 Campaign
        return Dimension.CAMPAIGN


class StrategyEngine:
    """
    策略引擎

    核心功能：
    1. 管理策略
    2. 基于生命周期记录匹配策略
    3. 生成基建决策
    """

    def __init__(self):
        self._strategies: dict[str, Strategy] = {}
        self._last_trigger_time: dict[str, datetime] = {}  # strategy_id -> last trigger time

    def add_strategy(self, strategy: Strategy) -> None:
        """添加策略"""
        self._strategies[strategy.id] = strategy

    def remove_strategy(self, strategy_id: str) -> None:
        """删除策略"""
        self._strategies.pop(strategy_id, None)

    def get_strategy(self, strategy_id: str) -> Strategy | None:
        """获取策略"""
        return self._strategies.get(strategy_id)

    def list_strategies(self, dimension: Dimension | None = None, enabled_only: bool = True) -> list[Strategy]:
        """列出策略"""
        strategies = list(self._strategies.values())
        if dimension:
            strategies = [s for s in strategies if s.dimension == dimension]
        if enabled_only:
            strategies = [s for s in strategies if s.enabled]
        return sorted(strategies, key=lambda s: s.name)

    def match_strategies(
        self,
        lifecycle_record: LifecycleRecord,
        additional_metrics: dict | None = None
    ) -> list[StrategyMatch]:
        """
        匹配策略

        Args:
            lifecycle_record: 生命周期记录
            additional_metrics: 额外指标（用于条件判断）

        Returns:
            匹配成功的策略列表
        """
        matches = []
        trigger_stage = TriggerStageMapper.to_trigger_stage(lifecycle_record.current_stage)
        dimension = TriggerStageMapper.get_dimension(trigger_stage)

        # 合并指标
        metrics = {**lifecycle_record.metrics_snapshot}
        if additional_metrics:
            metrics.update(additional_metrics)

        for strategy in self._strategies.values():
            # 检查是否启用
            if not strategy.enabled:
                continue

            # 检查维度
            if strategy.dimension != dimension:
                continue

            # 检查触发阶段
            if trigger_stage not in strategy.trigger_stages:
                continue

            # 检查冷却时间
            if strategy.id in self._last_trigger_time:
                last_time = self._last_trigger_time[strategy.id]
                if datetime.utcnow() - last_time < timedelta(hours=strategy.cooldown_hours):
                    continue

            # 检查时间窗口
            if not self._check_time_window(strategy):
                continue

            # 检查额外条件
            if not self._check_conditions(strategy.conditions, metrics):
                continue

            # 匹配成功
            match = StrategyMatch(
                strategy=strategy,
                entity_id=lifecycle_record.entity_id,
                entity_stage=trigger_stage,
                confidence=lifecycle_record.confidence,
                action=strategy.action,
                scale=strategy.scale,
                reason=f"阶段{trigger_stage.value}触发策略{strategy.name}"
            )
            matches.append(match)

        return matches

    def record_trigger(self, strategy_id: str) -> datetime:
        """记录策略触发时间（用于冷却）"""
        now = datetime.utcnow()
        self._last_trigger_time[strategy_id] = now
        return now

    def _check_time_window(self, strategy: Strategy) -> bool:
        """检查当前时间是否在允许的时间窗口内"""
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")

        if strategy.time_window_start <= current_time <= strategy.time_window_end:
            return True
        return True  # 默认允许

    def _check_conditions(self, conditions: list[Condition], metrics: dict) -> bool:
        """检查额外条件是否满足"""
        for cond in conditions:
            value = metrics.get(cond.field)
            if value is None:
                return False

            try:
                cond_value = float(cond.value)
                metric_value = float(value)

                if cond.operator == ">":
                    if not metric_value > cond_value:
                        return False
                elif cond.operator == "<":
                    if not metric_value < cond_value:
                        return False
                elif cond.operator == ">=":
                    if not metric_value >= cond_value:
                        return False
                elif cond.operator == "<=":
                    if not metric_value <= cond_value:
                        return False
                elif cond.operator == "==":
                    if not metric_value == cond_value:
                        return False
            except (ValueError, TypeError):
                return False

        return True


# =============================================================================
# 基建决策生成器
# =============================================================================

class DecisionGenerator:
    """
    决策生成器

    将策略匹配结果转换为具体的基建决策
    """

    @staticmethod
    def generate_decisions(matches: list[StrategyMatch]) -> list[dict]:
        """
        生成基建决策

        Args:
            matches: 策略匹配结果

        Returns:
            决策列表
        """
        decisions = []

        for match in matches:
            decision = {
                "timestamp": datetime.utcnow().isoformat(),
                "entity_id": match.entity_id,
                "entity_stage": match.entity_stage.value,
                "strategy_id": match.strategy.id,
                "strategy_name": match.strategy.name,
                "action": match.action.value,
                "confidence": match.confidence,
                "scale": DecisionGenerator._calculate_scale(match),
                "reason": match.reason,
            }
            decisions.append(decision)

        return decisions

    @staticmethod
    def _calculate_scale(match: StrategyMatch) -> int:
        """计算实际执行规模"""
        scale = match.scale

        if scale.type == "fixed":
            return int(scale.value)
        elif scale.type == "percentage":
            return int(scale.value)
        elif scale.type == "dynamic":
            return int(scale.value * match.confidence)

        return int(scale.value)


# =============================================================================
# 默认策略模板（基于ROI分析）
# =============================================================================

DEFAULT_STRATEGY_TEMPLATES = [
    # ========== Campaign 策略 ==========

    # Campaign-冷死亡 -> 饱和式攻击（最多创建50条）
    Strategy(
        id="campaign_cold_dead_burst",
        name="冷死亡-饱和攻击",
        description="Campaign从未产生收入，使用饱和式攻击补充",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_COLD_DEAD],
        conditions=[
            Condition(field="duration_hours", operator=">=", value=24)
        ],
        action=ActionType.GROWTH_BURST,
        scale=ScaleConfig(type="fixed", value=50, max_limit=100),
        cooldown_hours=24,
    ),

    # Campaign-冷启动 -> 复制替换（前24h ROI低）
    Strategy(
        id="campaign_cold_start_clone",
        name="冷启动-复制替换",
        description="Campaign前24h ROI < 10%，复制新广告测试",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_COLD_START],
        action=ActionType.CLONE_AD,
        scale=ScaleConfig(type="fixed", value=10, max_limit=20),
        cooldown_hours=12,
    ),

    # Campaign-验证期 -> 素材预热（持续观察）
    Strategy(
        id="campaign_verify_prepare",
        name="验证期-素材预热",
        description="Campaign处于验证期(ROI 10-40%)，预热新素材",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_VERIFY],
        action=ActionType.MATERIAL_PREPARE,
        scale=ScaleConfig(type="fixed", value=5, max_limit=10),
        cooldown_hours=48,
    ),

    # Campaign-成长期 -> 加预算（ROI > 40%）
    Strategy(
        id="campaign_growth_increase",
        name="成长期-增加预算",
        description="Campaign ROI > 40%进入成长期，增加预算扩大规模",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_GROWTH],
        conditions=[
            Condition(field="roi", operator=">", value=0.4)
        ],
        action=ActionType.INCREASE_BUDGET,
        scale=ScaleConfig(type="percentage", value=20, max_limit=50),
        cooldown_hours=72,
    ),

    # Campaign-持续盈利 -> 渠道扩张
    Strategy(
        id="campaign_sustained_expand",
        name="持续盈利-渠道扩张",
        description="Campaign持续盈利超过7天，横向扩张到其他渠道",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_SUSTAINED],
        action=ActionType.CHANNEL_EXPAND,
        scale=ScaleConfig(type="fixed", value=20, max_limit=30),
        cooldown_hours=168,
    ),

    # Campaign-衰退期 -> 有序关停
    Strategy(
        id="campaign_decline_shutdown",
        name="衰退期-有序关停",
        description="Campaign ROI下降超过50%，准备有序关停",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_DECLINE],
        action=ActionType.GRACEFUL_SHUTDOWN,
        scale=ScaleConfig(type="fixed", value=1, max_limit=5),
        cooldown_hours=24,
    ),

    # Campaign-衰退期 -> 基建补充
    Strategy(
        id="campaign_decline_rebuild",
        name="衰退期-基建补充",
        description="Campaign进入衰退期，启动新一轮基建",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_DECLINE],
        action=ActionType.REBUILD,
        scale=ScaleConfig(type="fixed", value=30, max_limit=50),
        cooldown_hours=72,
    ),

    # Campaign-关停期 -> 完全关停
    Strategy(
        id="campaign_shutdown_stop",
        name="关停期-停止投放",
        description="Campaign ROI < 10%持续72h+，关停并释放预算",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_SHUTDOWN],
        action=ActionType.GRACEFUL_SHUTDOWN,
        scale=ScaleConfig(type="fixed", value=1, max_limit=1),
        cooldown_hours=0,
    ),

    # ========== Product 策略 ==========

    # Product-盈利 -> 渠道扩张
    Strategy(
        id="product_profitable_expand",
        name="盈利商品-扩张",
        description="商品ROI > 40%，横向扩张到更多渠道",
        dimension=Dimension.PRODUCT,
        trigger_stages=[TriggerStage.PRODUCT_PROFITABLE],
        action=ActionType.CHANNEL_EXPAND,
        scale=ScaleConfig(type="fixed", value=20, max_limit=50),
        cooldown_hours=168,
    ),

    # Product-亏损 -> 基建补充
    Strategy(
        id="product_loss_rebuild",
        name="亏损商品-重建",
        description="商品ROI <= 40%，使用新素材重新创建广告",
        dimension=Dimension.PRODUCT,
        trigger_stages=[TriggerStage.PRODUCT_LOSS],
        action=ActionType.REBUILD,
        scale=ScaleConfig(type="fixed", value=30, max_limit=50),
        cooldown_hours=72,
    ),

]
