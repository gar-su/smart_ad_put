import json
from datetime import datetime
from pathlib import Path
from enum import Enum
from pydantic import BaseModel, Field
from config.settings import settings


class DecisionType(str, Enum):
    """决策类型"""
    CREATE_AD = "CREATE_AD"
    CLONE_AD = "CLONE_AD"
    PAUSE_AD = "PAUSE_AD"
    STOP_AD = "STOP_AD"
    ADJUST_BUDGET = "ADJUST_BUDGET"
    MATERIAL_PREHEAT = "MATERIAL_PREHEAT"
    STRATEGY_TRIGGER = "STRATEGY_TRIGGER"


class ActionType(str, Enum):
    """动作类型"""
    GROWTH_BURST = "GROWTH_BURST"           # 增长期：饱和式攻击
    CHANNEL_EXPAND = "CHANNEL_EXPAND"       # 渠道扩张
    BUDGET_SMOOTH = "BUDGET_SMOOTH"         # 稳定期：预算平滑
    MATERIAL_PREPARE = "MATERIAL_PREPARE"   # 素材预热
    GRACEFUL_SHUTDOWN = "GRACEFUL_SHUTDOWN" # 衰退期：有序关停
    REBUILD = "REBUILD"                     # 衰退期：基建补充


class Decision(BaseModel):
    """决策指令"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    decision_id: str
    type: DecisionType
    dimension: str  # product | material | ad_unit
    target_id: str
    action: ActionType
    payload: dict
    reason: str = ""
    confidence: float = 1.0


class DecisionCommander:
    """决策指挥官 - 输出决策到日志"""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or settings.DECISION_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def output(self, decision: Decision) -> Path:
        """输出决策到日志文件"""
        # 按日期分目录
        date_str = decision.timestamp.strftime("%Y-%m-%d")
        log_file = self.log_dir / date_str / f"decisions_{decision.timestamp.strftime('%H%M%S')}.json"

        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(decision.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        return log_file

    def output_batch(self, decisions: list[Decision]) -> list[Path]:
        """批量输出决策"""
        return [self.output(d) for d in decisions]

    def append_to_daily_log(self, decision: Decision) -> None:
        """追加到每日汇总日志"""
        date_str = decision.timestamp.strftime("%Y-%m-%d")
        daily_log = self.log_dir / date_str / "decisions.jsonl"

        daily_log.parent.mkdir(parents=True, exist_ok=True)

        with open(daily_log, "a", encoding="utf-8") as f:
            f.write(decision.model_dump_json() + "\n")
