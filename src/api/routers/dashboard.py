"""
Dashboard API
"""

from fastapi import APIRouter
from datetime import datetime, timedelta
import json
from pathlib import Path

from config.settings import settings

router = APIRouter()


@router.get("/summary")
async def dashboard_summary():
    """看板总览"""
    # 读取今日决策统计
    today_decisions = 0
    today_actions = {}
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = settings.DECISION_LOG_DIR / date_str / "decisions.jsonl"

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    decision = json.loads(line)
                    today_decisions += 1
                    action = decision.get("action", "unknown")
                    today_actions[action] = today_actions.get(action, 0) + 1
                except:
                    continue

    return {
        "total_products": 1944,  # 示例数据
        "total_campaigns": 109198,
        "active_decisions_today": today_decisions,
        "today_actions": today_actions,
        "system_status": "running",
        "last_update": datetime.utcnow().isoformat(),
    }


@router.get("/health")
async def product_health():
    """商品健康度仪表盘"""
    # 示例数据
    return {
        "total": 1944,
        "coverage": 0.85,
        "lifecycle_distribution": {
            "growth": 0.07,
            "mature": 0.07,
            "decline": 0.63,
            "cold_start": 0.22,
        },
        "alerts": [
            {"type": "warning", "message": "123个商品进入衰退期", "count": 123},
            {"type": "info", "message": "45个商品处于成长期", "count": 45},
        ],
        "products_needing_attention": [
            {"entity_id": "prod_001", "stage": "decline", "cost_change": -0.45},
            {"entity_id": "prod_002", "stage": "cold_start", "cost_first_24h": 30},
        ],
    }


@router.get("/material/utilization")
async def material_utilization():
    """素材利用率"""
    return {
        "total_materials": 0,
        "unused_materials": 0,
        "high_frequency_materials": [],
        "fatigue_warnings": [],
        "note": "素材数据暂未接入"
    }


@router.get("/efficiency")
async def efficiency_report():
    """基建效率报表"""
    # 读取最近7天决策
    decisions_by_day = {}
    for i in range(7):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        log_file = settings.DECISION_LOG_DIR / date_str / "decisions.jsonl"

        count = 0
        cold_start_count = 0
        decline_count = 0

        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        decision = json.loads(line)
                        count += 1
                        if "cold" in decision.get("stage", ""):
                            cold_start_count += 1
                        if "decline" in decision.get("stage", ""):
                            decline_count += 1
                    except:
                        continue

        decisions_by_day[date_str] = {
            "total": count,
            "cold_start_triggers": cold_start_count,
            "decline_triggers": decline_count,
        }

    return {
        "automation_rate": 0.68,
        "cold_start_success_rate": 0.72,
        "decisions_by_day": decisions_by_day,
        "total_decisions_this_week": sum(d["total"] for d in decisions_by_day.values()),
    }


@router.get("/lifecycle/distribution")
async def lifecycle_distribution(dimension: str = "product"):
    """生命周期阶段分布"""
    # 基于之前分析的数据
    if dimension == "product":
        return {
            "dimension": "product",
            "distribution": {
                "product_cold_start": 0.21,
                "product_growth": 0.06,
                "product_mature": 0.07,
                "product_decline": 0.66,
            },
            "total_entities": 1944,
        }
    else:
        return {
            "dimension": "campaign",
            "distribution": {
                "campaign_cold_dead": 0.64,
                "campaign_cold_start": 0.05,
                "campaign_growth": 0.09,
                "campaign_stable": 0.10,
                "campaign_decay": 0.12,
            },
            "total_entities": 109198,
        }


@router.get("/strategies/summary")
async def strategies_summary():
    """策略执行摘要"""
    return {
        "total_rules": 6,
        "enabled_rules": 5,
        "triggers_today": 12,
        "decisions_today": 45,
        "top_actions": [
            {"action": "GROWTH_BURST", "count": 20},
            {"action": "REBUILD", "count": 12},
            {"action": "CLONE_AD", "count": 8},
            {"action": "GRACEFUL_SHUTDOWN", "count": 5},
        ],
    }
