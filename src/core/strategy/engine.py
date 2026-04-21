"""
基建策略引擎

基于生命周期阶段匹配策略规则，生成基建决策

基于ROI的业务标准:
- 盈利标准: ROI > 40%
- 冷启动失败: 前24h ROI < 10%
- 关键决策点: 72小时
"""

from datetime import datetime, timedelta
from typing import Protocol, TypeVar

from .models import (
    StrategyRule,
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
            LifecycleStage.CAMPAIGN_COLD_DEAD: TriggerStage.CAMPAIGN_COLD_DEAD,
            LifecycleStage.CAMPAIGN_COLD_START: TriggerStage.CAMPAIGN_COLD_START,
            LifecycleStage.CAMPAIGN_VERIFY: TriggerStage.CAMPAIGN_VERIFY,
            LifecycleStage.CAMPAIGN_GROWTH: TriggerStage.CAMPAIGN_GROWTH,
            LifecycleStage.CAMPAIGN_SUSTAINED: TriggerStage.CAMPAIGN_SUSTAINED,
            LifecycleStage.CAMPAIGN_DECLINE: TriggerStage.CAMPAIGN_DECLINE,
            LifecycleStage.CAMPAIGN_SHUTDOWN: TriggerStage.CAMPAIGN_SHUTDOWN,
            # Product维度
            LifecycleStage.PRODUCT_PROFITABLE: TriggerStage.PRODUCT_PROFITABLE,
            LifecycleStage.PRODUCT_LOSS: TriggerStage.PRODUCT_LOSS,
            LifecycleStage.PRODUCT_DEAD: TriggerStage.PRODUCT_DEAD,
        }
        return mapping.get(lifecycle_stage, TriggerStage.CAMPAIGN_VERIFY)

    @staticmethod
    def get_dimension(stage: TriggerStage) -> Dimension:
        """获取阶段对应的维度"""
        if stage.value.startswith("campaign_"):
            return Dimension.CAMPAIGN
        elif stage.value.startswith("product_"):
            return Dimension.PRODUCT
        return Dimension.CAMPAIGN


class StrategyEngine:
    """
    策略引擎

    核心功能：
    1. 管理策略规则
    2. 基于生命周期记录匹配策略
    3. 生成基建决策
    """

    def __init__(self):
        self._rules: dict[str, StrategyRule] = {}
        self._last_trigger_time: dict[str, datetime] = {}  # rule_id -> last trigger time

    def add_rule(self, rule: StrategyRule) -> None:
        """添加策略规则"""
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> None:
        """删除策略规则"""
        self._rules.pop(rule_id, None)

    def get_rule(self, rule_id: str) -> StrategyRule | None:
        """获取策略规则"""
        return self._rules.get(rule_id)

    def list_rules(self, dimension: Dimension | None = None, enabled_only: bool = True) -> list[StrategyRule]:
        """列出策略规则"""
        rules = list(self._rules.values())
        if dimension:
            rules = [r for r in rules if r.dimension == dimension]
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return sorted(rules, key=lambda r: r.priority)

    def match_rules(
        self,
        lifecycle_record: LifecycleRecord,
        additional_metrics: dict | None = None
    ) -> list[StrategyMatch]:
        """
        匹配策略规则

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

        for rule in self._rules.values():
            # 检查是否启用
            if not rule.enabled:
                continue

            # 检查维度
            if rule.dimension != dimension:
                continue

            # 检查触发阶段
            if trigger_stage not in rule.trigger_stages:
                continue

            # 检查置信度
            if lifecycle_record.confidence < rule.confidence_min:
                continue

            # 检查冷却时间
            if rule.id in self._last_trigger_time:
                last_time = self._last_trigger_time[rule.id]
                if datetime.utcnow() - last_time < timedelta(hours=rule.cooldown_hours):
                    continue

            # 检查时间窗口
            if not self._check_time_window(rule):
                continue

            # 检查额外条件
            if not self._check_conditions(rule.conditions, metrics):
                continue

            # 匹配成功
            match = StrategyMatch(
                rule=rule,
                entity_id=lifecycle_record.entity_id,
                entity_stage=trigger_stage,
                confidence=lifecycle_record.confidence * rule.confidence_min,
                action=rule.action,
                scale=rule.scale,
                reason=f"阶段{trigger_stage.value}触发规则{rule.name}"
            )
            matches.append(match)

        # 按优先级排序
        matches.sort(key=lambda m: m.rule.priority)
        return matches

    def trigger_rule(self, rule_id: str) -> datetime:
        """记录规则触发时间（用于冷却）"""
        now = datetime.utcnow()
        self._last_trigger_time[rule_id] = now
        return now

    def _check_time_window(self, rule: StrategyRule) -> bool:
        """检查当前时间是否在允许的时间窗口内"""
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")

        if rule.time_window_start <= current_time <= rule.time_window_end:
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
                "rule_id": match.rule.id,
                "rule_name": match.rule.name,
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
    StrategyRule(
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
        priority=10,
        cooldown_hours=24,
    ),

    # Campaign-冷启动 -> 复制替换（前24h ROI低）
    StrategyRule(
        id="campaign_cold_start_clone",
        name="冷启动-复制替换",
        description="Campaign前24h ROI < 10%，复制新广告测试",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_COLD_START],
        action=ActionType.CLONE_AD,
        scale=ScaleConfig(type="fixed", value=10, max_limit=20),
        priority=15,
        cooldown_hours=12,
    ),

    # Campaign-验证期 -> 素材预热（持续观察）
    StrategyRule(
        id="campaign_verify_prepare",
        name="验证期-素材预热",
        description="Campaign处于验证期(ROI 10-40%)，预热新素材",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_VERIFY],
        action=ActionType.MATERIAL_PREPARE,
        scale=ScaleConfig(type="fixed", value=5, max_limit=10),
        priority=30,
        cooldown_hours=48,
    ),

    # Campaign-成长期 -> 加预算（ROI > 40%）
    StrategyRule(
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
        priority=20,
        cooldown_hours=72,
    ),

    # Campaign-持续盈利 -> 渠道扩张
    StrategyRule(
        id="campaign_sustained_expand",
        name="持续盈利-渠道扩张",
        description="Campaign持续盈利超过7天，横向扩张到其他渠道",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_SUSTAINED],
        action=ActionType.CHANNEL_EXPAND,
        scale=ScaleConfig(type="fixed", value=20, max_limit=30),
        priority=25,
        cooldown_hours=168,
    ),

    # Campaign-衰退期 -> 有序关停
    StrategyRule(
        id="campaign_decline_shutdown",
        name="衰退期-有序关停",
        description="Campaign ROI下降超过50%，准备有序关停",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_DECLINE],
        action=ActionType.GRACEFUL_SHUTDOWN,
        scale=ScaleConfig(type="fixed", value=1, max_limit=5),
        priority=15,
        cooldown_hours=24,
    ),

    # Campaign-衰退期 -> 基建补充
    StrategyRule(
        id="campaign_decline_rebuild",
        name="衰退期-基建补充",
        description="Campaign进入衰退期，启动新一轮基建",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_DECLINE],
        action=ActionType.REBUILD,
        scale=ScaleConfig(type="fixed", value=30, max_limit=50),
        priority=20,
        cooldown_hours=72,
    ),

    # Campaign-关停期 -> 完全关停
    StrategyRule(
        id="campaign_shutdown_stop",
        name="关停期-停止投放",
        description="Campaign ROI < 10%持续72h+，关停并释放预算",
        dimension=Dimension.CAMPAIGN,
        trigger_stages=[TriggerStage.CAMPAIGN_SHUTDOWN],
        action=ActionType.GRACEFUL_SHUTDOWN,
        scale=ScaleConfig(type="fixed", value=1, max_limit=1),
        priority=5,
        cooldown_hours=0,
    ),

    # ========== Product 策略 ==========

    # Product-盈利 -> 渠道扩张
    StrategyRule(
        id="product_profitable_expand",
        name="盈利商品-扩张",
        description="商品ROI > 40%，横向扩张到更多渠道",
        dimension=Dimension.PRODUCT,
        trigger_stages=[TriggerStage.PRODUCT_PROFITABLE],
        action=ActionType.CHANNEL_EXPAND,
        scale=ScaleConfig(type="fixed", value=20, max_limit=50),
        priority=20,
        cooldown_hours=168,
    ),

    # Product-亏损 -> 基建补充
    StrategyRule(
        id="product_loss_rebuild",
        name="亏损商品-重建",
        description="商品ROI <= 40%，使用新素材重新创建广告",
        dimension=Dimension.PRODUCT,
        trigger_stages=[TriggerStage.PRODUCT_LOSS],
        action=ActionType.REBUILD,
        scale=ScaleConfig(type="fixed", value=30, max_limit=50),
        priority=30,
        cooldown_hours=72,
    ),

    # Product-无收入 -> 放弃
    StrategyRule(
        id="product_dead_abandon",
        name="无收入商品-放弃",
        description="商品完全无收入，放弃并寻找替代品",
        dimension=Dimension.PRODUCT,
        trigger_stages=[TriggerStage.PRODUCT_DEAD],
        action=ActionType.GRACEFUL_SHUTDOWN,
        scale=ScaleConfig(type="fixed", value=1, max_limit=1),
        priority=5,
        cooldown_hours=0,
    ),
]
