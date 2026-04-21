"""
基建策略模型

定义策略规则的配置结构

基于ROI的生命周期阶段:
- Campaign: cold_dead, cold_start, verify, growth, sustained, decline, shutdown
- Product: profitable, loss, dead
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List


class Dimension(str, Enum):
    """策略适用的维度"""
    PRODUCT = "product"
    CAMPAIGN = "campaign"


class TriggerStage(str, Enum):
    """
    触发阶段（基于ROI）

    Campaign维度:
    - cold_dead: 冷死亡，从未产生收入
    - cold_start: 冷启动，前24h ROI < 10%
    - verify: 验证期，24-72h ROI在10-40%
    - growth: 成长期，72h后ROI > 40%
    - sustained: 持续盈利，ROI > 40% 超过7天
    - decline: 衰退期，ROI从高点下降 > 50%
    - shutdown: 关停期，ROI < 10% 持续72h+

    Product维度:
    - profitable: 盈利，ROI > 40%
    - loss: 亏损，ROI <= 40%
    - dead: 无收入
    """

    # Campaign维度
    CAMPAIGN_COLD_DEAD = "campaign_cold_dead"
    CAMPAIGN_COLD_START = "campaign_cold_start"
    CAMPAIGN_VERIFY = "campaign_verify"
    CAMPAIGN_GROWTH = "campaign_growth"
    CAMPAIGN_SUSTAINED = "campaign_sustained"
    CAMPAIGN_DECLINE = "campaign_decline"
    CAMPAIGN_SHUTDOWN = "campaign_shutdown"

    # Product维度
    PRODUCT_PROFITABLE = "product_profitable"
    PRODUCT_LOSS = "product_loss"
    PRODUCT_DEAD = "product_dead"


class ActionType(str, Enum):
    """
    基建动作类型

    基于数据分析的业务建议:
    - 盈利Campaign(CAMPAIGN_GROWTH/SUSTAINED): 加预算、渠道扩张
    - 验证期Campaign(CAMPAIGN_VERIFY): 持续观察、素材预热
    - 亏损Campaign(CAMPAIGN_COLD_START/COLD_DEAD): 饱和攻击、复制替换
    - 衰退Campaign(CAMPAIGN_DECLINE): 有序关停、基建补充
    """

    # 增长期动作
    GROWTH_BURST = "GROWTH_BURST"           # 饱和式攻击
    CHANNEL_EXPAND = "CHANNEL_EXPAND"       # 渠道扩张
    CLONE_AD = "CLONE_AD"                   # 复制广告
    INCREASE_BUDGET = "INCREASE_BUDGET"     # 增加预算

    # 稳定期动作
    BUDGET_SMOOTH = "BUDGET_SMOOTH"         # 预算平滑
    MATERIAL_PREPARE = "MATERIAL_PREPARE"    # 素材预热
    MAINTAIN = "MAINTAIN"                   # 维持现状

    # 衰退期动作
    GRACEFUL_SHUTDOWN = "GRACEFUL_SHUTDOWN"  # 有序关停
    REBUILD = "REBUILD"                       # 基建补充
    REDUCE_BUDGET = "REDUCE_BUDGET"           # 降低预算


class Condition(BaseModel):
    """条件配置"""
    field: str = Field(description="字段名: roi, revenue, cost, duration等")
    operator: str = Field(description="操作符: >, <, >=, <=, ==")
    value: float = Field(description="阈值")


class ScaleConfig(BaseModel):
    """规模配置"""
    type: str = Field(default="fixed", description="fixed|percentage|dynamic")
    value: float = Field(description="数量或百分比")
    max_limit: int = Field(default=100, description="最大限制")


class StrategyRule(BaseModel):
    """基建策略规则"""
    id: str
    name: str
    description: str = ""

    # 触发条件
    dimension: Dimension
    trigger_stages: List[TriggerStage] = Field(description="触发的生命周期阶段")
    conditions: List[Condition] = Field(default_factory=list, description="额外条件")
    confidence_min: float = Field(default=0.7, description="最小置信度")

    # 执行动作
    action: ActionType
    scale: ScaleConfig = Field(default_factory=lambda: ScaleConfig(type="fixed", value=10))

    # 规则控制
    enabled: bool = True
    priority: int = Field(default=100, description="优先级，数字越小越高")

    # 时间控制
    cooldown_hours: int = Field(default=24, description="触发冷却时间(小时)")
    time_window_start: str = Field(default="00:00", description="允许触发的时间窗口开始")
    time_window_end: str = Field(default="23:59", description="允许触发的时间窗口结束")

    created_at: str = ""
    updated_at: str = ""


class StrategyMatch(BaseModel):
    """策略匹配结果"""
    rule: StrategyRule
    entity_id: str
    entity_stage: TriggerStage
    confidence: float
    action: ActionType
    scale: ScaleConfig
    reason: str = ""
