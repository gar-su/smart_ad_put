"""跟投信号主循环（smart_ad_put 本期唯一产出）

数据源: data/video_daily/*.json（按日 top50 短剧视频指标）
流程: 每视频按日聚合 → 生命周期判定 → 阶段→信号映射＋冷却 → 落盘

运行:  uv run python run_pipeline.py
输出:  logs/decisions/YYYY-MM-DD/decisions.jsonl（与决策日志同一目录/格式）
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypedDict

from config.settings import settings
from src.core.lifecycle.detector import ProductLifecycleDetector
from src.core.lifecycle.stages import Dimension, LifecycleRecord
from src.core.signal import BuildSignal, BuildSignalGenerator, StageSignalMapper
from src.core.signal.config import SignalRules

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "video_daily"
SIGNAL_RULES_PATH = BASE_DIR / "config" / "signal_rules.json"


class _VideoAgg(TypedDict):
    """单视频跨天聚合态"""

    rois: list[float]
    revenue: float
    cost: float
    lang: str
    script: str
    name: str
    first: date | None
    last: date | None


def parse_roi(value: object) -> float:
    """解析 '43.72%' → 0.4372；解析失败记 0（数据源已确认无缺失）"""
    s = str(value).strip().strip("%")
    try:
        return float(s) / 100.0
    except ValueError:
        return 0.0


def load_daily_rows() -> list[tuple[date, list[dict[str, Any]]]]:
    """读 data/video_daily/*.json，按文件名日期升序返回"""
    days: list[tuple[date, list[dict[str, Any]]]] = []
    for f in sorted(DATA_DIR.glob("*.json")):
        with open(f) as fp:
            payload: dict[str, Any] = json.load(fp)
        expected = date.fromisoformat(Path(f).stem)
        if payload["date"] != expected.isoformat():
            raise ValueError(f"{f} 日期与文件名不一致")
        days.append((expected, payload["rows"]))
    return days


def append_signal(signal: BuildSignal, out_dir: Path) -> None:
    """追加一行信号到 logs/decisions/YYYY-MM-DD/decisions.jsonl"""
    day_dir = out_dir / datetime.now(UTC).strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    with open(day_dir / "decisions.jsonl", "a") as fp:
        fp.write(json.dumps(signal.model_dump(mode="json"), ensure_ascii=False) + "\n")


def main() -> None:
    detector = ProductLifecycleDetector()
    rules = SignalRules.load(SIGNAL_RULES_PATH)  # 配置缺失时用内置默认（§5.5.2）
    generator = BuildSignalGenerator(
        cooldown_hours=rules.cooldown_hours,
        mapper=StageSignalMapper(rules.follow_up_stages),
    )

    daily_rows = load_daily_rows()
    if not daily_rows:
        raise ValueError(f"{DATA_DIR} 下无数据文件")

    def new_agg() -> _VideoAgg:
        return _VideoAgg(
            rois=[], revenue=0.0, cost=0.0, lang="", script="", name="", first=None, last=None
        )

    by_video: dict[str, _VideoAgg] = {}
    for day, rows in daily_rows:
        for row in rows:
            vid = str(row["videoId"])
            agg = by_video.setdefault(vid, new_agg())
            agg["rois"].append(parse_roi(row["roi"]))
            agg["revenue"] += float(row["rechargeAmt"])
            agg["cost"] += float(row["cost"])
            if not agg["lang"]:
                agg["lang"] = str(row.get("language") or "")
            if not agg["script"]:
                agg["script"] = str(row.get("videoRemark") or "")
            if not agg["name"]:
                agg["name"] = str(row.get("videoName") or "")
            if agg["first"] is None:
                agg["first"] = day
            agg["last"] = day

    emitted = 0
    stages: dict[str, int] = {}
    for vid, agg in by_video.items():
        first = agg["first"]
        last = agg["last"]
        if first is None or last is None:
            continue  # 防御：无观测日的视频不判
        span_days = (last - first).days + 1  # 观测跨度，含首尾
        result = detector.detect(
            total_revenue=agg["revenue"],
            total_cost=agg["cost"],
            campaign_count=0,  # top50 视频维度，无 campaign 计数
            duration_hours=span_days * 24,
            recent_roi_history=agg["rois"],
        )
        stages[result.stage.value] = stages.get(result.stage.value, 0) + 1
        lifecycle = LifecycleRecord(
            dimension=Dimension.PRODUCT,
            entity_id=vid,
            current_stage=result.stage,
            stage_entered_at=datetime.now(UTC),
            metrics_snapshot=result.metrics or {},
            confidence=result.confidence,
            detection_reason=result.reason,
        )
        signal = generator.generate(
            lifecycle,
            language_code=agg["lang"],
            script_no=agg["script"],
            shortplay_name=agg["name"],
        )
        if signal:
            append_signal(signal, settings.DECISION_LOG_DIR)
            emitted += 1
            print(
                f"  + {signal.signal_id} [{signal.signal_type.value}] {vid} "
                f"{signal.shortplay_name or agg['script'] or ''} roi_reason={signal.reason}"
            )

    print(f"videos={len(by_video)} signals={emitted}")
    print("stage_dist =", {k: stages[k] for k in sorted(stages)})


if __name__ == "__main__":
    main()
