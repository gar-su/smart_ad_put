"""
策略管理 API

基于ROI的业务标准:
- 盈利标准: ROI > 40%
- 冷启动失败: 前24h ROI < 10%
- 关键决策点: 72小时
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.core.strategy.models import (
    Strategy,
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
for strategy in DEFAULT_STRATEGY_TEMPLATES:
    strategy_engine.add_strategy(strategy)


# ============ 请求/响应模型 ============

class CreateStrategyRequest(BaseModel):
    name: str
    description: str = ""
    dimension: str
    trigger_stages: List[str]
    conditions: List[dict] = []
    action: str
    scale_value: float = 10
    scale_max_limit: int = 100
    cooldown_hours: int = 24
    enabled: bool = True


class UpdateStrategyRequest(CreateStrategyRequest):
    pass


class MatchRequest(BaseModel):
    entity_id: str
    dimension: str
    current_stage: str
    confidence: float = 0.8
    metrics: dict = {}


# ============ 策略管理 API ============

@router.get("/strategies")
async def list_strategies(dimension: Optional[str] = None, enabled_only: bool = True):
    """获取策略列表"""
    dim = Dimension(dimension) if dimension else None
    strategies = strategy_engine.list_strategies(dimension=dim, enabled_only=enabled_only)
    return {
        "strategies": [s.model_dump() for s in strategies],
        "total": len(strategies)
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """获取单个策略"""
    strategy = strategy_engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return strategy.model_dump()


@router.post("/strategies")
async def create_strategy(req: CreateStrategyRequest):
    """创建策略"""
    strategy = Strategy(
        id=f"strategy_{datetime.utcnow().timestamp()}",
        name=req.name,
        description=req.description,
        dimension=Dimension(req.dimension),
        trigger_stages=[TriggerStage(s) for s in req.trigger_stages],
        conditions=[Condition(**c) for c in req.conditions],
        action=ActionType(req.action),
        scale=ScaleConfig(type="fixed", value=req.scale_value, max_limit=req.scale_max_limit),
        cooldown_hours=req.cooldown_hours,
        enabled=req.enabled,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )
    strategy_engine.add_strategy(strategy)
    return {"id": strategy.id, "status": "created"}


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, req: UpdateStrategyRequest):
    """更新策略"""
    existing = strategy_engine.get_strategy(strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="策略不存在")

    updated = Strategy(
        id=strategy_id,
        name=req.name,
        description=req.description,
        dimension=Dimension(req.dimension),
        trigger_stages=[TriggerStage(s) for s in req.trigger_stages],
        conditions=[Condition(**c) for c in req.conditions],
        action=ActionType(req.action),
        scale=ScaleConfig(type="fixed", value=req.scale_value, max_limit=req.scale_max_limit),
        cooldown_hours=req.cooldown_hours,
        enabled=req.enabled,
        created_at=existing.created_at,
        updated_at=datetime.utcnow().isoformat(),
    )
    strategy_engine.add_strategy(updated)
    return {"id": strategy_id, "status": "updated"}


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    if not strategy_engine.get_strategy(strategy_id):
        raise HTTPException(status_code=404, detail="策略不存在")
    strategy_engine.remove_strategy(strategy_id)
    return {"id": strategy_id, "status": "deleted"}


@router.post("/strategies/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str, enabled: bool):
    """启用/禁用策略"""
    strategy = strategy_engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    strategy.enabled = enabled
    return {"id": strategy_id, "enabled": enabled}


# ============ 策略匹配 API ============

@router.post("/match")
async def match_strategies(req: MatchRequest):
    """匹配策略"""
    # 生命周期阶段映射（基于ROI）
    stage_map = {
        # Campaign维度
        "campaign_cold_dead": Stage.CAMPAIGN_COLD_DEAD,
        "campaign_cold_start": Stage.CAMPAIGN_COLD_START,
        "campaign_verify": Stage.CAMPAIGN_VERIFY,
        "campaign_growth": Stage.CAMPAIGN_GROWTH,
        "campaign_sustained": Stage.CAMPAIGN_SUSTAINED,
        "campaign_decline": Stage.CAMPAIGN_DECLINE,
        "campaign_shutdown": Stage.CAMPAIGN_SHUTDOWN,
        # Product维度
        "product_profitable": Stage.PRODUCT_PROFITABLE,
        "product_loss": Stage.PRODUCT_LOSS,
    }

    dimension_map = {
        "product": LifecycleDimension.PRODUCT,
        "campaign": LifecycleDimension.CAMPAIGN,
    }

    lifecycle_record = LifecycleRecord(
        dimension=dimension_map.get(req.dimension, LifecycleDimension.CAMPAIGN),
        entity_id=req.entity_id,
        current_stage=stage_map.get(req.current_stage, Stage.CAMPAIGN_VERIFY),
        stage_entered_at=datetime.utcnow(),
        metrics_snapshot=req.metrics,
        confidence=req.confidence,
    )

    matches = strategy_engine.match_strategies(lifecycle_record, req.metrics)

    # 记录触发时间
    for match in matches:
        strategy_engine.record_trigger(match.strategy.id)

    # 生成决策
    decisions = DecisionGenerator.generate_decisions(matches)

    return {
        "matches": [
            {
                "strategy_id": m.strategy.id,
                "strategy_name": m.strategy.name,
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
            }
            for t in DEFAULT_STRATEGY_TEMPLATES
        ]
    }
