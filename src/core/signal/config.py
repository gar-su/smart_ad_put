"""信号规则配置（阶段→信号映射 + 冷却时长）

配置源: config/signal_rules.json（单文件、纳入版本控制）。
pipeline 每次运行读取；API 通过 GET/PUT /api/signals/config 读写同一文件；
保存后下次 pipeline 运行生效（批量脚本，无热重载）。
"""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from src.core.lifecycle.stages import Stage

# 默认值得跟投的阶段（PRD §5.5.2：入库/成长期/稳定期；material 挂起）
DEFAULT_FOLLOW_UP_STAGES: list[str] = [
    Stage.PRODUCT_ENTRY.value,
    Stage.PRODUCT_GROWTH.value,
    Stage.PRODUCT_SUSTAINED.value,
    Stage.CAMPAIGN_GROWTH.value,
    Stage.CAMPAIGN_SUSTAINED.value,
]

# API 展示用阶段中文名（覆盖 product_*/campaign_*，material 本期无数据不列出）
STAGE_LABELS: dict[str, str] = {
    Stage.CAMPAIGN_OBSERVING.value: "待观察",
    Stage.CAMPAIGN_COLD_DEAD.value: "冷死亡",
    Stage.CAMPAIGN_COLD_START.value: "冷启动",
    Stage.CAMPAIGN_VERIFY.value: "验证期",
    Stage.CAMPAIGN_GROWTH.value: "成长期",
    Stage.CAMPAIGN_SUSTAINED.value: "持续盈利",
    Stage.CAMPAIGN_DECLINE.value: "衰退期",
    Stage.CAMPAIGN_SHUTDOWN.value: "关停期",
    Stage.PRODUCT_OBSERVING.value: "待观察",
    Stage.PRODUCT_ENTRY.value: "入场期",
    Stage.PRODUCT_SUSTAINED.value: "稳定期",
    Stage.PRODUCT_GROWTH.value: "成长期",
    Stage.PRODUCT_DECLINE.value: "衰退期",
    Stage.PRODUCT_EXIT.value: "退出期",
}


class SignalRules(BaseModel):
    """信号规则配置（pipeline 与 API 共用的唯一配置源）"""

    follow_up_stages: list[str] = Field(
        default_factory=lambda: list(DEFAULT_FOLLOW_UP_STAGES),
        description="值得跟投（FOLLOW_UP）的生命周期阶段，须为 Stage 合法值",
    )
    cooldown_hours: int = Field(default=24, gt=0, description="同一目标同类型信号冷却时长（小时）")

    @field_validator("follow_up_stages")
    @classmethod
    def _check_stages_valid(cls, value: list[str]) -> list[str]:
        """阶段名必须可解析为 Stage，非法名立即失败（fast-fail）"""
        for name in value:
            Stage(name)  # 非法阶段名抛 ValueError → pydantic ValidationError
        return value

    @classmethod
    def load(cls, path: Path) -> SignalRules:
        """从 JSON 读取；文件不存在时返回内置默认规则"""
        if not path.exists():
            return cls()
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> None:
        """原子写回 JSON：同目录临时文件写后 os.replace，避免半截文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".signal_rules.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(self.model_dump_json(indent=2) + "\n")
            os.replace(tmp_path, path)
        except BaseException:
            with suppress(OSError):
                os.unlink(tmp_path)
            raise


def available_stages() -> list[dict[str, str]]:
    """可选阶段（product_*/campaign_*，排除 material 本期无数据支撑）"""
    return [
        {"value": s.value, "label": STAGE_LABELS.get(s.value, s.name)}
        for s in Stage
        if s.value.startswith(("product_", "campaign_"))
    ]
