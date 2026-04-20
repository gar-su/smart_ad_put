"""
自动化基建 API

基于生命周期检测和策略匹配，生成基建决策
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json

from config.settings import settings
from src.core.lifecycle.detector import ProductLifecycleDetector, CampaignLifecycleDetector
from src.core.lifecycle.stages import LifecycleRecord, Dimension
from src.core.strategy.engine import StrategyEngine, DecisionGenerator, DEFAULT_STRATEGY_TEMPLATES

router = APIRouter()

# 初始化
product_detector = ProductLifecycleDetector()
campaign_detector = CampaignLifecycleDetector()
strategy_engine = StrategyEngine()

for rule in DEFAULT_STRATEGY_TEMPLATES:
    strategy_engine.add_rule(rule)


# ============ 请求模型 ============

class ProductLifecycleRequest(BaseModel):
    """商品生命周期检测请求"""
    entity_id: str
    duration_hours: float
    cost_first_24h: float
    cost_last_24h: float
    cost_change_pct: float
    ctr_first_24h: float | None = None
    total_pays: int = 0


class CampaignLifecycleRequest(BaseModel):
    """Campaign生命周期检测请求"""
    entity_id: str
    duration_hours: float
    cost_first_24h: float
    cost_last_24h: float
    cost_change_pct: float
    cost_per_hour: float | None = None
    ctr_first_24h: float | None = None
    total_pays: int = 0


class TriggerRequest(BaseModel):
    """触发自动化请求"""
    dimension: str  # product | campaign
    entity_id: str


# ============ 生命周期检测 API ============

@router.post("/lifecycle/product/detect")
async def detect_product_lifecycle(req: ProductLifecycleRequest):
    """检测商品生命周期阶段"""
    result = product_detector.detect(
        duration_hours=req.duration_hours,
        cost_first_24h=req.cost_first_24h,
        cost_last_24h=req.cost_last_24h,
        cost_change_pct=req.cost_change_pct,
        ctr_first_24h=req.ctr_first_24h,
        total_pays=req.total_pays,
    )

    # 构建生命周期记录
    lifecycle_record = LifecycleRecord(
        dimension=Dimension.PRODUCT,
        entity_id=req.entity_id,
        current_stage=result.stage,
        stage_entered_at=datetime.utcnow(),
        metrics_snapshot=result.metrics,
        confidence=result.confidence,
        detection_reason=result.reason,
    )

    return {
        "entity_id": req.entity_id,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": result.metrics,
        "lifecycle_record": lifecycle_record.model_dump(),
    }


@router.post("/lifecycle/campaign/detect")
async def detect_campaign_lifecycle(req: CampaignLifecycleRequest):
    """检测Campaign生命周期阶段"""
    result = campaign_detector.detect(
        duration_hours=req.duration_hours,
        cost_first_24h=req.cost_first_24h,
        cost_last_24h=req.cost_last_24h,
        cost_change_pct=req.cost_change_pct,
        cost_per_hour=req.cost_per_hour,
        ctr_first_24h=req.ctr_first_24h,
        total_pays=req.total_pays,
    )

    lifecycle_record = LifecycleRecord(
        dimension=Dimension.CAMPAIGN,
        entity_id=req.entity_id,
        current_stage=result.stage,
        stage_entered_at=datetime.utcnow(),
        metrics_snapshot=result.metrics,
        confidence=result.confidence,
        detection_reason=result.reason,
    )

    return {
        "entity_id": req.entity_id,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": result.metrics,
        "lifecycle_record": lifecycle_record.model_dump(),
    }


# ============ 策略匹配 API ============

@router.post("/trigger")
async def trigger_automation(
    req: TriggerRequest,
    background_tasks: BackgroundTasks
):
    """
    触发自动化基建

    完整的流程:
    1. 生命周期检测
    2. 策略匹配
    3. 决策输出
    """
    dimension = req.dimension
    entity_id = req.entity_id

    # 这里需要传入实际的指标数据
    # 简化版本：使用请求中的基本信息

    # 匹配策略
    # 注意：实际使用时需要先检测生命周期，再匹配
    # 这里简化处理，直接返回策略列表

    rules = strategy_engine.list_rules(
        dimension=dimension,
        enabled_only=True
    )

    return {
        "entity_id": entity_id,
        "dimension": dimension,
        "matched_rules": [
            {
                "id": r.id,
                "name": r.name,
                "action": r.action.value,
                "scale": r.scale.value,
            }
            for r in rules[:5]  # 最多返回5条
        ],
        "status": "ready",
    }


@router.post("/decision/output")
async def output_decision(
    entity_id: str,
    dimension: str,
    stage: str,
    action: str,
    scale: int,
    reason: str = "",
):
    """
    输出基建决策到日志文件

    这是决策的最终输出点
    """
    decision = {
        "timestamp": datetime.utcnow().isoformat(),
        "entity_id": entity_id,
        "dimension": dimension,
        "stage": stage,
        "action": action,
        "scale": scale,
        "reason": reason,
    }

    # 输出到日志文件
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_dir = settings.DECISION_LOG_DIR / date_str
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "decisions.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")

    # 同时输出详细JSON
    detail_file = log_dir / f"decision_{datetime.utcnow().strftime('%H%M%S')}.json"
    with open(detail_file, "w", encoding="utf-8") as f:
        json.dump(decision, f, ensure_ascii=False, indent=2)

    return {
        "status": "output",
        "decision": decision,
        "log_file": str(log_file),
    }


# ============ 批量处理 API ============

@router.post("/batch/process")
async def batch_process(
    dimension: str,
    entities: list[dict],
    background_tasks: BackgroundTasks,
):
    """
    批量处理实体

    接收一批实体，批量进行生命周期检测和策略匹配
    """
    results = []

    for entity in entities:
        entity_id = entity.get("entity_id")
        if not entity_id:
            continue

        # 检测生命周期
        if dimension == "product":
            req = ProductLifecycleRequest(
                entity_id=entity_id,
                duration_hours=entity.get("duration_hours", 0),
                cost_first_24h=entity.get("cost_first_24h", 0),
                cost_last_24h=entity.get("cost_last_24h", 0),
                cost_change_pct=entity.get("cost_change_pct", 0),
                total_pays=entity.get("total_pays", 0),
            )
            lifecycle_result = await detect_product_lifecycle(req)
        else:
            req = CampaignLifecycleRequest(
                entity_id=entity_id,
                duration_hours=entity.get("duration_hours", 0),
                cost_first_24h=entity.get("cost_first_24h", 0),
                cost_last_24h=entity.get("cost_last_24h", 0),
                cost_change_pct=entity.get("cost_change_pct", 0),
                total_pays=entity.get("total_pays", 0),
            )
            lifecycle_result = await detect_campaign_lifecycle(req)

        results.append(lifecycle_result)

    return {
        "dimension": dimension,
        "total": len(entities),
        "processed": len(results),
        "results": results,
    }


# ============ 决策统计 API ============

@router.get("/decisions/stats")
async def get_decision_stats(days: int = 7):
    """
    获取决策统计

    统计最近N天的决策情况
    """
    stats = {
        "total_decisions": 0,
        "by_action": {},
        "by_stage": {},
        "recent_decisions": [],
    }

    # 读取最近N天的决策日志
    for i in range(days):
        date = datetime.utcnow().replace(day=datetime.utcnow().day - i)
        date_str = date.strftime("%Y-%m-%d")
        log_file = settings.DECISION_LOG_DIR / date_str / "decisions.jsonl"

        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        decision = json.loads(line)
                        stats["total_decisions"] += 1

                        action = decision.get("action", "unknown")
                        stats["by_action"][action] = stats["by_action"].get(action, 0) + 1

                        stage = decision.get("stage", "unknown")
                        stats["by_stage"][stage] = stats["by_stage"].get(stage, 0) + 1

                        stats["recent_decisions"].append(decision)
                    except json.JSONDecodeError:
                        continue

    # 只保留最近100条
    stats["recent_decisions"] = stats["recent_decisions"][-100:]

    return stats
