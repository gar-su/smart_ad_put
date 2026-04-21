"""
生命周期阶段定义

基于数据分析验证的阈值（业务标准: ROI > 40% 为盈利）

关键发现:
- 72小时是判断Campaign生死的关键节点
- 前24h ROI < 10% 的Campaign，85%最终无法盈利
- 盈利Campaign的订单收入占比 > 90%
- 49%的存活>7天的Campaign能盈利

参考: src/core/lifecycle/VALIDATION_REPORT.md
"""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel


class Dimension(str, Enum):
    """生命周期维度"""
    PRODUCT = "product"       # 商品维度（短剧）
    MATERIAL = "material"     # 素材维度（暂无数据支撑）
    CAMPAIGN = "campaign"   # 广告单元维度（campaign）


class Stage(str, Enum):
    """
    生命周期阶段（基于ROI的业务标准）

    核心指标: ROI = (d0_order_amt + d0_ad_amt) / cost_h
    盈利标准: ROI > 40%
    """

    # ========== Campaign 维度 ==========
    CAMPAIGN_OBSERVING = "campaign_observing"       # 待观察：投放<24h，时间不足无法判断

    # 冷启动失败类
    CAMPAIGN_COLD_DEAD = "campaign_cold_dead"      # 冷死亡：投放>72h且从未产生收入
    CAMPAIGN_COLD_START = "campaign_cold_start"    # 冷启动：前24h ROI < 10%

    # 验证期（24-72h）
    CAMPAIGN_VERIFY = "campaign_verify"            # 验证期：24-72h ROI在10-40%，关键决策点

    # 盈利类
    CAMPAIGN_GROWTH = "campaign_growth"            # 成长期：72h后ROI > 40%
    CAMPAIGN_SUSTAINED = "campaign_sustained"       # 持续盈利：ROI > 40% 超过7天

    # 衰退类
    CAMPAIGN_DECLINE = "campaign_decline"          # 衰退期：ROI从高点下降 > 50%
    CAMPAIGN_SHUTDOWN = "campaign_shutdown"         # 关停期：ROI < 10% 持续72h+

    # ========== 商品（ShortPlay）维度 ==========
    # 基于回测数据验证的阈值：近3天ROI>40% 精确率87%，近5天ROI在30%-80% 精确率86%
    PRODUCT_OBSERVING = "product_observing"       # 待观察：投放 < 3天，时间不足
    PRODUCT_ENTRY = "product_entry"               # 入场：近3天ROI均值 > 40%
    PRODUCT_SUSTAINED = "product_sustained"       # 稳定：近5天ROI在30%-80%波动
    PRODUCT_GROWTH = "product_growth"             # 成长：ROI > 40% 且趋势上升
    PRODUCT_DECLINE = "product_decline"           # 衰退：ROI持续下滑 > 30%
    PRODUCT_EXIT = "product_exit"                 # 退出：ROI < 10% 持续 5天
    PRODUCT_DEAD = "product_dead"                 # 无投放：cost = 0

    # ========== 素材维度（暂无数据支撑，基于行业经验）==========
    MATERIAL_FRESH = "material_fresh"               # 新鲜期
    MATERIAL_GOLDEN = "material_golden"             # 黄金期
    MATERIAL_FATIGUE = "material_fatigue"          # 疲劳期
    MATERIAL_ELIMINATED = "material_eliminated"     # 淘汰期


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
