"""建造信号查询 API

供看板/调试读取 logs/decisions/ 下的信号输出（与 machine-delivery 对接前，
下游通过该通道消费 FOLLOW_UP 等建造信号）。
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from config.settings import settings
from src.core.signal.config import SignalRules, available_stages

router = APIRouter()

# 信号规则配置（pipeline 与 API 共用同一文件）
SIGNAL_RULES_PATH = settings.BASE_DIR / "config" / "signal_rules.json"


def _today_file() -> Path:
    """今日信号文件（与 pipeline 落盘 UTC 日对齐）"""
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return settings.DECISION_LOG_DIR / date_str / "decisions.jsonl"


@router.get("")
async def list_signals() -> dict[str, Any]:
    """今日全部建造信号（按落盘顺序）"""
    f = _today_file()
    if not f.exists():
        return {"signals": [], "total": 0}
    signals: list[dict[str, Any]] = []
    with open(f, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            signals.append(json.loads(line))
    return {"signals": signals, "total": len(signals)}


@router.get("/stats")
async def signal_stats() -> dict[str, Any]:
    """今日信号统计：按 signal_type 分布"""
    f = _today_file()
    by_type: dict[str, int] = {}
    total = 0
    if f.exists():
        with open(f, encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                total += 1
                st = json.loads(line).get("signal_type", "unknown")
                by_type[st] = by_type.get(st, 0) + 1
    return {"total": total, "by_signal_type": by_type}


@router.get("/config")
async def get_signal_config() -> dict[str, Any]:
    """信号规则配置读取（含可选阶段列表，供前端配置页渲染）"""
    return {
        "rules": SignalRules.load(SIGNAL_RULES_PATH).model_dump(),
        "available_stages": available_stages(),
    }


@router.put("/config")
async def put_signal_config(payload: SignalRules) -> dict[str, Any]:
    """信号规则保存（校验 + 原子写回，下次 pipeline 运行生效）"""
    payload.save(SIGNAL_RULES_PATH)
    return {"saved": True}
