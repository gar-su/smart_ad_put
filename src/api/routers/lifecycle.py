"""
生命周期管理 API
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from src.core.lifecycle.detector import ProductLifecycleDetector, CampaignLifecycleDetector
from src.core.lifecycle.stages import Stage

router = APIRouter()

product_detector = ProductLifecycleDetector()
campaign_detector = CampaignLifecycleDetector()


class ProductDetectRequest(BaseModel):
    entity_id: str
    duration_hours: float
    cost_first_24h: float
    cost_last_24h: float
    cost_change_pct: float
    ctr_first_24h: Optional[float] = None
    total_pays: int = 0


class CampaignDetectRequest(BaseModel):
    entity_id: str
    duration_hours: float
    cost_first_24h: float
    cost_last_24h: float
    cost_change_pct: float
    cost_per_hour: Optional[float] = None
    ctr_first_24h: Optional[float] = None
    total_pays: int = 0


@router.post("/product/detect")
async def detect_product_lifecycle(req: ProductDetectRequest):
    """
    检测商品生命周期阶段

    基于数据分析验证的阈值:
    - duration <= 24h AND cost < 50 → cold_start
    - cost_change > +20% → growth
    - cost_change < -30% → decline
    - -20% <= cost_change <= +20% AND cost >= 200 → mature
    """
    result = product_detector.detect(
        duration_hours=req.duration_hours,
        cost_first_24h=req.cost_first_24h,
        cost_last_24h=req.cost_last_24h,
        cost_change_pct=req.cost_change_pct,
        ctr_first_24h=req.ctr_first_24h,
        total_pays=req.total_pays,
    )

    return {
        "entity_id": req.entity_id,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": result.metrics,
        "survival_probability": product_detector.get_survival_probability(req.cost_first_24h),
    }


@router.post("/campaign/detect")
async def detect_campaign_lifecycle(req: CampaignDetectRequest):
    """
    检测广告单元（Campaign）生命周期阶段

    基于数据分析验证的阈值:
    - duration <= 24h AND cost < 50 → cold_dead
    - duration <= 24h → cold_start
    - cost_change > +20% → growth
    - -30% <= cost_change <= +30% → stable
    - cost_change < -30% → decay
    - cost_per_hour < 1 AND duration > 48 → shutdown
    """
    result = campaign_detector.detect(
        duration_hours=req.duration_hours,
        cost_first_24h=req.cost_first_24h,
        cost_last_24h=req.cost_last_24h,
        cost_change_pct=req.cost_change_pct,
        cost_per_hour=req.cost_per_hour,
        ctr_first_24h=req.ctr_first_24h,
        total_pays=req.total_pays,
    )

    return {
        "entity_id": req.entity_id,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": result.metrics,
        "survival_probability": campaign_detector.get_survival_probability(req.cost_first_24h),
    }


@router.get("/stages")
async def list_stages(dimension: str = Query(..., description="维度: product 或 campaign")):
    """获取指定维度的所有生命周期阶段"""
    if dimension == "product":
        return {
            "dimension": "product",
            "stages": [
                {"value": "product_cold_start", "label": "冷启动失败", "description": "首日消耗<50元且时长<24h"},
                {"value": "product_introducing", "label": "引入期", "description": "刚上线，数据不足"},
                {"value": "product_growth", "label": "成长期", "description": "消耗增长>20%"},
                {"value": "product_mature", "label": "成熟期", "description": "消耗稳定在±20%"},
                {"value": "product_decline", "label": "衰退期", "description": "消耗下降>30%"},
            ]
        }
    else:
        return {
            "dimension": "campaign",
            "stages": [
                {"value": "campaign_cold_dead", "label": "冷死亡", "description": "24h内死亡且消耗<50元"},
                {"value": "campaign_cold_start", "label": "冷启动", "description": "存活但<24h"},
                {"value": "campaign_growth", "label": "增长期", "description": "消耗增长>20%"},
                {"value": "campaign_stable", "label": "稳定期", "description": "消耗变化在±30%"},
                {"value": "campaign_decay", "label": "衰退期", "description": "消耗下降>30%"},
                {"value": "campaign_shutdown", "label": "关停期", "description": "每小时<1元，持续>48h"},
            ]
        }


@router.get("/thresholds")
async def get_thresholds():
    """获取当前配置的阈值"""
    return {
        "product": {
            "COLD_START_DURATION_HOURS": 24,
            "COST_CRITICAL": 50,
            "COST_HEALTHY": 500,
            "GROWTH_COST_CHANGE_MIN": 0.20,
            "MATURE_COST_CHANGE_RANGE": [-0.20, 0.20],
            "DECAY_COST_CHANGE_MAX": -0.30,
        },
        "campaign": {
            "COLD_START_DURATION_HOURS": 24,
            "COST_CRITICAL": 50,
            "COST_HEALTHY": 200,
            "STABLE_COST_CHANGE_RANGE": [-0.30, 0.30],
            "DECAY_COST_DROP_MIN": 0.30,
            "SHUTDOWN_COST_PER_HOUR_MAX": 1.0,
        }
    }
