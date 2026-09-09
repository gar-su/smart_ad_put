"""生命周期判定 API

服务只做判定：输入实体的历史原子事实，输出它当前所处的生命周期阶段。
不做信号、不存储、不取数（接口契约见 PRD §5.9）。

基于ROI的业务标准:
- 盈利标准: ROI > 40%
- 冷启动失败: 前24h ROI < 10%
- 关键决策点: 72小时
"""

import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.core.lifecycle.aggregation import (
    DailyFact,
    FactValidationError,
    HourlyFact,
    aggregate_campaign,
    aggregate_product,
)
from src.core.lifecycle.detector import (
    CampaignLifecycleDetector,
    CostThresholds,
    DetectionResult,
    ProductLifecycleDetector,
    RevenueThresholds,
    ROIThresholds,
)
from src.core.lifecycle.stages import Dimension

router = APIRouter()

# 批量检测单次上限（PRD §6.1）
MAX_BATCH_ENTITIES = 1000

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


class FactRecord(BaseModel):
    """单条原子事实（字段名对齐数据契约 docs/data_contract.md §3）"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    date: datetime.date = Field(description="数据归属日")
    hour: int | None = Field(default=None, ge=0, le=23, description="campaign 维度必填")
    spend: float = Field(ge=0, description="消耗")
    income_order: float = Field(alias="incomeOrder", ge=0, description="订单（充值）收入")
    income_ad: float = Field(alias="incomeAd", ge=0, description="广告分成（IAA）收入")


class DetectRequest(BaseModel):
    """单实体判定请求"""

    entity_id: str = Field(min_length=1, description="实体标识（短剧视频 ID / campaign ID）")
    records: list[FactRecord] = Field(min_length=1, description="按时间升序的原子事实，不可断档")


class BatchDetectRequest(BaseModel):
    """批量判定请求（PRD §6.1：支持 1000+ 实体/次）"""

    dimension: Literal["product", "campaign"]
    entities: list[DetectRequest] = Field(min_length=1, max_length=MAX_BATCH_ENTITIES)


def _payload(
    entity_id: str,
    dimension: Dimension,
    result: DetectionResult,
    roi: float,
    revenue: float,
    cost: float,
    duration_hours: float,
) -> dict[str, Any]:
    """统一响应体：判定结论 + 判定用到的派生指标"""
    return {
        "entity_id": entity_id,
        "dimension": dimension.value,
        "stage": result.stage.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "metrics": {
            **result.metrics,
            "roi": roi,
            "revenue": revenue,
            "cost": cost,
            "duration_hours": duration_hours,
        },
    }


def _product_result(entity_id: str, records: list[FactRecord]) -> dict[str, Any]:
    """短剧维度判定"""
    try:
        metrics = aggregate_product(
            [
                DailyFact(
                    date=r.date,
                    spend=r.spend,
                    income_order=r.income_order,
                    income_ad=r.income_ad,
                )
                for r in records
            ]
        )
    except FactValidationError as exc:
        raise HTTPException(status_code=400, detail={"entity_id": entity_id, "message": str(exc)}) from exc

    result = product_detector.detect(
        total_revenue=metrics.total_revenue,
        total_cost=metrics.total_cost,
        campaign_count=0,  # 原子事实里没有关联 Campaign 计数
        duration_hours=metrics.duration_hours,
        order_amt=metrics.order_amt,
        ad_amt=metrics.ad_amt,
        recent_roi_history=metrics.recent_roi_history,
    )
    roi = metrics.total_revenue / metrics.total_cost if metrics.total_cost > 0 else 0.0
    return _payload(
        entity_id, Dimension.PRODUCT, result, roi, metrics.total_revenue, metrics.total_cost, metrics.duration_hours
    )


def _campaign_result(entity_id: str, records: list[FactRecord]) -> dict[str, Any]:
    """广告单元维度判定（分段收入/成本由小时记录聚合得出）"""
    hourly: list[HourlyFact] = []
    for r in records:
        if r.hour is None:
            raise HTTPException(
                status_code=400,
                detail={"entity_id": entity_id, "message": "campaign 维度的 records 必须带 hour"},
            )
        hourly.append(
            HourlyFact(
                date=r.date,
                hour=r.hour,
                spend=r.spend,
                income_order=r.income_order,
                income_ad=r.income_ad,
            )
        )

    try:
        metrics = aggregate_campaign(hourly)
    except FactValidationError as exc:
        raise HTTPException(status_code=400, detail={"entity_id": entity_id, "message": str(exc)}) from exc

    result = campaign_detector.detect(
        duration_hours=metrics.duration_hours,
        revenue=metrics.revenue,
        cost=metrics.cost,
        revenue_0_24h=metrics.revenue_0_24h,
        cost_0_24h=metrics.cost_0_24h,
        revenue_24_72h=metrics.revenue_24_72h,
        cost_24_72h=metrics.cost_24_72h,
        revenue_72plus=metrics.revenue_72plus,
        cost_72plus=metrics.cost_72plus,
        order_amt=metrics.order_amt,
        ad_amt=metrics.ad_amt,
    )
    roi = metrics.revenue / metrics.cost if metrics.cost > 0 else 0.0
    return _payload(entity_id, Dimension.CAMPAIGN, result, roi, metrics.revenue, metrics.cost, metrics.duration_hours)


@router.post("/product/detect")
async def detect_product_lifecycle(req: DetectRequest) -> dict[str, Any]:
    """
    检测短剧（product）生命周期阶段

    判定基于 ROI = (incomeOrder + incomeAd) / spend：
    - observing: 投放 < 3天
    - entry: 近3天ROI均值 > 40%（入场信号）
    - sustained: 近5天ROI在30%-80%波动（稳定信号）
    - growth: ROI > 40% 且趋势上升
    - decline: ROI持续下滑 > 30%
    - exit: ROI < 10% 持续5天
    """
    return _product_result(req.entity_id, req.records)


@router.post("/campaign/detect")
async def detect_campaign_lifecycle(req: DetectRequest) -> dict[str, Any]:
    """
    检测广告单元（campaign）生命周期阶段

    分段收入/成本由小时记录按距首条记录的小时偏移聚合：
    < 24h、24-72h、≥ 72h。

    阶段说明:
    - cold_dead: 冷死亡，总收入=0
    - cold_start: 冷启动，前24h ROI < 10%
    - verify: 验证期，24-72h ROI在10-40%
    - growth: 成长期，72h后ROI > 40%
    - sustained: 持续盈利，ROI > 40% 超过7天
    - decline: 衰退期，ROI从高点下降 > 50%
    - shutdown: 关停期，ROI < 10% 持续72h+
    """
    return _campaign_result(req.entity_id, req.records)


@router.post("/detect/batch")
async def detect_batch(req: BatchDetectRequest) -> dict[str, Any]:
    """批量判定：同一维度下多个实体，单次上限 1000 个（PRD §6.1）"""
    detect = _product_result if req.dimension == "product" else _campaign_result
    results = [detect(entity.entity_id, entity.records) for entity in req.entities]
    return {"dimension": req.dimension, "total": len(results), "results": results}


@router.get("/stages")
async def list_stages(dimension: str = Query(..., description="维度: product 或 campaign")) -> dict[str, Any]:
    """获取指定维度的所有生命周期阶段"""

    # Campaign阶段（基于ROI）
    campaign_stages = [
        {"value": "campaign_observing", "label": "待观察", "description": "投放 < 24h，时间不足无法判断"},
        {"value": "campaign_cold_dead", "label": "冷死亡", "description": "投放 > 72h且从未产生收入"},
        {"value": "campaign_cold_start", "label": "冷启动", "description": "前24h ROI < 10%，风险高"},
        {"value": "campaign_verify", "label": "验证期", "description": "24-72h ROI在10-40%，关键决策点"},
        {"value": "campaign_growth", "label": "成长期", "description": "72h后ROI > 40%，进入盈利阶段"},
        {"value": "campaign_sustained", "label": "持续盈利", "description": "ROI > 40% 超过7天"},
        {"value": "campaign_decline", "label": "衰退期", "description": "ROI从高点下降超过50%"},
        {"value": "campaign_shutdown", "label": "关停期", "description": "ROI < 10% 持续72h+"},
    ]

    # Product阶段（基于回测数据）
    product_stages = [
        {"value": "product_observing", "label": "待观察", "description": "投放 < 3天，时间不足"},
        {"value": "product_entry", "label": "入场期", "description": "近3天ROI均值 > 40%，入场信号"},
        {"value": "product_sustained", "label": "稳定期", "description": "近5天ROI均在30%-80%之间"},
        {"value": "product_growth", "label": "成长期", "description": "ROI > 40% 且趋势上升"},
        {"value": "product_decline", "label": "衰退期", "description": "ROI持续下滑 > 30%"},
        {"value": "product_exit", "label": "退出期", "description": "ROI < 10% 持续5天"},
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
async def get_thresholds() -> dict[str, Any]:
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
