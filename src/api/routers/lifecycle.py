"""
生命周期管理 API

基于ROI的业务标准:
- 盈利标准: ROI > 40%
- 冷启动失败: 前24h ROI < 10%
- 关键决策点: 72小时
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from src.core.lifecycle.detector import (
    CampaignLifecycleDetector,
    ProductLifecycleDetector,
    ROIThresholds,
    CostThresholds,
    RevenueThresholds,
)
from src.core.lifecycle.stages import Stage

router = APIRouter()

# 初始化检测器（使用新的ROI阈值）
campaign_detector = CampaignLifecycleDetector(
    roi_thresholds=ROIThresholds(),
    cost_thresholds=CostThresholds(),
    revenue_thresholds=RevenueThresholds(),
)
product_detector = ProductLifecycleDetector(
    roi_thresholds=ROIThresholds(),
    cost_thresholds=CostThresholds(),
)


class CampaignDetectRequest(BaseModel):
    """Campaign生命周期检测请求"""
    entity_id: str
    duration_hours: float

    # 收入数据
    revenue: float = 0                    # 总收入 (d0_order_amt + d0_ad_amt)
    cost: float = 0                      # 总成本
    revenue_0_24h: float = 0            # 前24小时收入
    cost_0_24h: float = 0              # 前24小时成本
    revenue_24_72h: float = 0           # 24-72小时收入
    cost_24_72h: float = 0              # 24-72小时成本
    revenue_72plus: float = 0           # 72小时后收入
    cost_72plus: float = 0              # 72小时后成本

    # 收入构成
    order_amt: float = 0                # 订单收入 (d0_order_amt)
    ad_amt: float = 0                   # 广告收入 (d0_ad_amt)

    # 可选指标
    cost_per_hour: Optional[float] = None
    ctr_first_24h: Optional[float] = None
    total_pays: int = 0


class ProductDetectRequest(BaseModel):
    """Product生命周期检测请求"""
    entity_id: str

    # 汇总数据
    total_revenue: float = 0             # 总收入
    total_cost: float = 0                # 总成本
    campaign_count: int = 0              # 关联Campaign数
    duration_hours: float = 0            # 最大投放时长

    # 收入构成
    order_amt: float = 0                # 订单收入
    ad_amt: float = 0                   # 广告收入


@router.post("/campaign/detect")
async def detect_campaign_lifecycle(req: CampaignDetectRequest):
    """
    检测广告单元（Campaign）生命周期阶段

    基于ROI的判定逻辑:
    - ROI = 收入 / 成本
    - 盈利标准: ROI > 40%
    - 冷启动失败: 前24h ROI < 10%
    - 关键决策点: 72小时

    阶段说明:
    - cold_dead: 冷死亡，总收入=0
    - cold_start: 冷启动，前24h ROI < 10%
    - verify: 验证期，24-72h ROI在10-40%
    - growth: 成长期，72h后ROI > 40%
    - sustained: 持续盈利，ROI > 40% 超过7天
    - decline: 衰退期，ROI从高点下降 > 50%
    - shutdown: 关停期，ROI < 10% 持续72h+
    """
    result = campaign_detector.detect(
        duration_hours=req.duration_hours,
        revenue=req.revenue,
        cost=req.cost,
        revenue_0_24h=req.revenue_0_24h,
        cost_0_24h=req.cost_0_24h,
        revenue_24_72h=req.revenue_24_72h,
        cost_24_72h=req.cost_24_72h,
        revenue_72plus=req.revenue_72plus,
        cost_72plus=req.cost_72plus,
        order_amt=req.order_amt,
        ad_amt=req.ad_amt,
    )

    # 计算ROI
    roi = req.revenue / req.cost if req.cost > 0 else 0
    roi_0_24h = req.revenue_0_24h / req.cost_0_24h if req.cost_0_24h > 0 else 0

    return {
        "entity_id": req.entity_id,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": result.metrics,
        "roi": {
            "total": roi,
            "roi_0_24h": roi_0_24h,
            "is_profitable": roi > 0.40,
        },
        "profitability_probability": campaign_detector.get_profitability_probability(roi_0_24h),
    }


@router.post("/product/detect")
async def detect_product_lifecycle(req: ProductDetectRequest):
    """
    检测商品（ShortPlay）生命周期阶段

    基于ROI的判定逻辑:
    - profitable: ROI > 40%
    - loss: ROI <= 40%
    - dead: 总收入=0
    """
    result = product_detector.detect(
        total_revenue=req.total_revenue,
        total_cost=req.total_cost,
        campaign_count=req.campaign_count,
        duration_hours=req.duration_hours,
        order_amt=req.order_amt,
        ad_amt=req.ad_amt,
    )

    roi = req.total_revenue / req.total_cost if req.total_cost > 0 else 0
    order_ratio = req.order_amt / req.total_revenue if req.total_revenue > 0 else 0

    return {
        "entity_id": req.entity_id,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": result.metrics,
        "roi": {
            "total": roi,
            "is_profitable": roi > 0.40,
        },
        "revenue_breakdown": {
            "order_amt": req.order_amt,
            "ad_amt": req.ad_amt,
            "order_ratio": order_ratio,
        },
    }


@router.get("/stages")
async def list_stages(dimension: str = Query(..., description="维度: product 或 campaign")):
    """获取指定维度的所有生命周期阶段"""

    # Campaign阶段（基于ROI）
    campaign_stages = [
        {"value": "campaign_cold_dead", "label": "冷死亡", "description": "从未产生收入，ROI=0"},
        {"value": "campaign_cold_start", "label": "冷启动", "description": "前24h ROI < 10%，风险高"},
        {"value": "campaign_verify", "label": "验证期", "description": "24-72h ROI在10-40%，关键决策点"},
        {"value": "campaign_growth", "label": "成长期", "description": "72h后ROI > 40%，进入盈利阶段"},
        {"value": "campaign_sustained", "label": "持续盈利", "description": "ROI > 40% 超过7天"},
        {"value": "campaign_decline", "label": "衰退期", "description": "ROI从高点下降超过50%"},
        {"value": "campaign_shutdown", "label": "关停期", "description": "ROI < 10% 持续72h+"},
    ]

    # Product阶段（基于ROI）
    product_stages = [
        {"value": "product_profitable", "label": "盈利", "description": "ROI > 40%"},
        {"value": "product_loss", "label": "亏损", "description": "ROI <= 40%"},
        {"value": "product_dead", "label": "无收入", "description": "总收入=0"},
    ]

    if dimension == "product":
        return {
            "dimension": "product",
            "stages": product_stages,
        }
    else:
        return {
            "dimension": "campaign",
            "stages": campaign_stages,
        }


@router.get("/thresholds")
async def get_thresholds():
    """获取当前配置的ROI阈值"""
    return {
        "roi": {
            "PROFITABLE_ROI": 0.40,      # 40% = 盈利线
            "ROI_VERY_LOW": 0.10,        # < 10% = 极低
            "ROI_LOW": 0.20,             # < 20% = 低
            "ROI_MEDIUM": 0.40,          # < 40% = 中等
        },
        "time": {
            "COLD_START_HOURS": 24,       # 冷启动期
            "VERIFY_HOURS": 72,            # 验证期
            "SUSTAINED_DAYS": 7,          # 持续盈利判定天数
        },
        "description": {
            "profit_threshold": "ROI > 40% 为盈利",
            "cold_start_threshold": "前24h ROI < 10% 为冷启动失败",
            "critical_point": "72小时是判断生死的关键节点",
            "revenue_formula": "收入 = d0_order_amt + d0_ad_amt",
        }
    }
