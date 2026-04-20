from enum import Enum
from datetime import datetime
from pydantic import BaseModel


class Dimension(str, Enum):
    """生命周期维度"""
    PRODUCT = "product"       # 商品维度（短剧）
    MATERIAL = "material"     # 素材维度（暂无数据）
    CAMPAIGN = "campaign"     # 广告单元维度（campaign）


class Stage(str, Enum):
    """生命周期阶段"""

    # ========== 商品（短剧）维度 ==========
    PRODUCT_INTRODUCING = "product_introducing"   # 引入期：上架<24h
    PRODUCT_GROWTH = "product_growth"             # 成长期：消耗增长>20%
    PRODUCT_MATURE = "product_mature"             # 成熟期：消耗稳定
    PRODUCT_DECLINE = "product_decline"           # 衰退期：消耗下降>30%
    PRODUCT_COLD_START = "product_cold_start"     # 冷启动失败：24h内停止

    # ========== 素材维度（暂无数据支撑）==========
    MATERIAL_FRESH = "material_fresh"           # 新鲜期
    MATERIAL_GOLDEN = "material_golden"         # 黄金期
    MATERIAL_FATIGUE = "material_fatigue"       # 疲劳期
    MATERIAL_ELIMINATED = "material_eliminated"  # 淘汰期

    # ========== 广告单元（Campaign）维度 ==========
    CAMPAIGN_COLD_DEAD = "campaign_cold_dead"     # 冷死亡：24h内死亡且消耗<50
    CAMPAIGN_COLD_START = "campaign_cold_start"  # 冷启动：存活但<24h
    CAMPAIGN_GROWTH = "campaign_growth"           # 增长期
    CAMPAIGN_STABLE = "campaign_stable"         # 稳定投放期
    CAMPAIGN_DECAY = "campaign_decay"           # 衰退期
    CAMPAIGN_SHUTDOWN = "campaign_shutdown"     # 关停期


class LifecycleRecord(BaseModel):
    """生命周期记录"""
    dimension: Dimension
    entity_id: str
    current_stage: Stage
    previous_stage: Stage | None = None
    stage_entered_at: datetime
    metrics_snapshot: dict = {}
    confidence: float = 1.0  # 判定置信度
    detection_reason: str = ""  # 判定原因说明
