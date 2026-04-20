"""
策略管理 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.core.strategy.models import (
    StrategyRule,
    StrategyMatch,
    Dimension,
    TriggerStage,
    ActionType,
    Condition,
    ScaleConfig,
)
from src.core.strategy.engine import StrategyEngine, DecisionGenerator, DEFAULT_STRATEGY_TEMPLATES
from src.core.lifecycle.stages import LifecycleRecord, Dimension as LifecycleDimension, Stage

router = APIRouter()

# 全局策略引擎实例
strategy_engine = StrategyEngine()

# 初始化默认策略
for rule in DEFAULT_STRATEGY_TEMPLATES:
    strategy_engine.add_rule(rule)


# ============ 请求/响应模型 ============

class CreateRuleRequest(BaseModel):
    name: str
    description: str = ""
    dimension: str
    trigger_stages: List[str]
    conditions: List[dict] = []
    action: str
    scale_value: float = 10
    scale_max_limit: int = 100
    confidence_min: float = 0.7
    priority: int = 100
    cooldown_hours: int = 24
    enabled: bool = True


class UpdateRuleRequest(CreateRuleRequest):
    pass


class MatchRequest(BaseModel):
    entity_id: str
    dimension: str
    current_stage: str
    confidence: float = 0.8
    metrics: dict = {}


# ============ 策略管理 API ============

@router.get("/rules")
async def list_rules(dimension: Optional[str] = None, enabled_only: bool = True):
    """获取策略规则列表"""
    dim = Dimension(dimension) if dimension else None
    rules = strategy_engine.list_rules(dimension=dim, enabled_only=enabled_only)
    return {
        "rules": [rule.model_dump() for rule in rules],
        "total": len(rules)
    }


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str):
    """获取单个策略规则"""
    rule = strategy_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule.model_dump()


@router.post("/rules")
async def create_rule(req: CreateRuleRequest):
    """创建策略规则"""
    rule = StrategyRule(
        id=f"rule_{datetime.utcnow().timestamp()}",
        name=req.name,
        description=req.description,
        dimension=Dimension(req.dimension),
        trigger_stages=[TriggerStage(s) for s in req.trigger_stages],
        conditions=[Condition(**c) for c in req.conditions],
        action=ActionType(req.action),
        scale=ScaleConfig(type="fixed", value=req.scale_value, max_limit=req.scale_max_limit),
        confidence_min=req.confidence_min,
        priority=req.priority,
        cooldown_hours=req.cooldown_hours,
        enabled=req.enabled,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )
    strategy_engine.add_rule(rule)
    return {"id": rule.id, "status": "created"}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, req: UpdateRuleRequest):
    """更新策略规则"""
    existing = strategy_engine.get_rule(rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="规则不存在")

    updated = StrategyRule(
        id=rule_id,
        name=req.name,
        description=req.description,
        dimension=Dimension(req.dimension),
        trigger_stages=[TriggerStage(s) for s in req.trigger_stages],
        conditions=[Condition(**c) for c in req.conditions],
        action=ActionType(req.action),
        scale=ScaleConfig(type="fixed", value=req.scale_value, max_limit=req.scale_max_limit),
        confidence_min=req.confidence_min,
        priority=req.priority,
        cooldown_hours=req.cooldown_hours,
        enabled=req.enabled,
        created_at=existing.created_at,
        updated_at=datetime.utcnow().isoformat(),
    )
    strategy_engine.add_rule(updated)
    return {"id": rule_id, "status": "updated"}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """删除策略规则"""
    if not strategy_engine.get_rule(rule_id):
        raise HTTPException(status_code=404, detail="规则不存在")
    strategy_engine.remove_rule(rule_id)
    return {"id": rule_id, "status": "deleted"}


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str, enabled: bool):
    """启用/禁用规则"""
    rule = strategy_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule.enabled = enabled
    return {"id": rule_id, "enabled": enabled}


# ============ 策略匹配 API ============

@router.post("/match")
async def match_rules(req: MatchRequest):
    """匹配策略规则"""
    # 构建生命周期记录
    stage_map = {
        "product_cold_start": Stage.PRODUCT_COLD_START,
        "product_introducing": Stage.PRODUCT_INTRODUCING,
        "product_growth": Stage.PRODUCT_GROWTH,
        "product_mature": Stage.PRODUCT_MATURE,
        "product_decline": Stage.PRODUCT_DECLINE,
        "campaign_cold_dead": Stage.CAMPAIGN_COLD_DEAD,
        "campaign_cold_start": Stage.CAMPAIGN_COLD_START,
        "campaign_growth": Stage.CAMPAIGN_GROWTH,
        "campaign_stable": Stage.CAMPAIGN_STABLE,
        "campaign_decay": Stage.CAMPAIGN_DECAY,
        "campaign_shutdown": Stage.CAMPAIGN_SHUTDOWN,
    }

    dimension_map = {
        "product": LifecycleDimension.PRODUCT,
        "campaign": LifecycleDimension.CAMPAIGN,
    }

    lifecycle_record = LifecycleRecord(
        dimension=dimension_map.get(req.dimension, LifecycleDimension.PRODUCT),
        entity_id=req.entity_id,
        current_stage=stage_map.get(req.current_stage, Stage.PRODUCT_INTRODUCING),
        stage_entered_at=datetime.utcnow(),
        metrics_snapshot=req.metrics,
        confidence=req.confidence,
    )

    matches = strategy_engine.match_rules(lifecycle_record, req.metrics)

    # 记录触发时间
    for match in matches:
        strategy_engine.trigger_rule(match.rule.id)

    # 生成决策
    decisions = DecisionGenerator.generate_decisions(matches)

    return {
        "matches": [
            {
                "rule_id": m.rule.id,
                "rule_name": m.rule.name,
                "action": m.action.value,
                "scale": m.scale.value,
                "confidence": m.confidence,
            }
            for m in matches
        ],
        "decisions": decisions,
    }


# ============ 策略模板 API ============

@router.get("/templates")
async def list_templates():
    """获取策略模板列表"""
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "dimension": t.dimension.value,
                "trigger_stages": [s.value for s in t.trigger_stages],
                "action": t.action.value,
                "scale": {"value": t.scale.value, "max_limit": t.scale.max_limit},
                "priority": t.priority,
            }
            for t in DEFAULT_STRATEGY_TEMPLATES
        ]
    }
