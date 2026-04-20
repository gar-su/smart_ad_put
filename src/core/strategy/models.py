"""
基建策略模型

定义策略规则的配置结构
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List


class Dimension(str, Enum):
    """策略适用的维度"""
    PRODUCT = "product"
    CAMPAIGN = "campaign"


class TriggerStage(str, Enum):
    """触发阶段"""

    # 商品维度
    PRODUCT_COLD_START = "product_cold_start"
    PRODUCT_INTRODUCING = "product_introducing"
    PRODUCT_GROWTH = "product_growth"
    PRODUCT_MATURE = "product_mature"
    PRODUCT_DECLINE = "product_decline"

    # Campaign维度
    CAMPAIGN_COLD_DEAD = "campaign_cold_dead"
    CAMPAIGN_COLD_START = "campaign_cold_start"
    CAMPAIGN_GROWTH = "campaign_growth"
    CAMPAIGN_STABLE = "campaign_stable"
    CAMPAIGN_DECAY = "campaign_decay"
    CAMPAIGN_SHUTDOWN = "campaign_shutdown"


class ActionType(str, Enum):
    """基建动作类型"""
    # 增长期动作
    GROWTH_BURST = "GROWTH_BURST"           # 饱和式攻击
    CHANNEL_EXPAND = "CHANNEL_EXPAND"         # 渠道扩张
    CLONE_AD = "CLONE_AD"                   # 复制广告

    # 稳定期动作
    BUDGET_SMOOTH = "BUDGET_SMOOTH"           # 预算平滑
    MATERIAL_PREPARE = "MATERIAL_PREPARE"      # 素材预热

    # 衰退期动作
    GRACEFUL_SHUTDOWN = "GRACEFUL_SHUTDOWN"  # 有序关停
    REBUILD = "REBUILD"                       # 基建补充


class Condition(BaseModel):
    """条件配置"""
    field: str = Field(description="字段名: cost, ctr, duration, total_pays等")
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
