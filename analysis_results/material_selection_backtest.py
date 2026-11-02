"""素材选择策略回测

数据源：short-drama-scoring/data/material_daily_v2.csv（素材 × 自然日）
判定逻辑：src/core/lifecycle 的 MaterialLifecycleDetector（与生产同源，不用模型）
标签：观测点之后活跃日的合并 ROI >= 40%（收入 = 订单充值 + IAA 广告分成）
评估：按 material_id 哈希切 70/30，素材不跨校准集/留出集；单票评估

用法：
    uv run python analysis_results/material_selection_backtest.py
    uv run python analysis_results/material_selection_backtest.py --data <csv>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from src.core.lifecycle.aggregation import MaterialFact, aggregate_material
from src.core.lifecycle.detector import MaterialLifecycleDetector, MaterialThresholds
from src.core.lifecycle.stages import Stage

DEFAULT_DATA = Path("/Users/gar/short-drama-scoring/data/material_daily_v2.csv")
REPORT_PATH = Path(__file__).parent / "material_selection" / "REPORT.md"

BREAKEVEN_ROI = 0.40
HOLDOUT_PCT = 30
CHECKPOINTS = (3, 5)
FOLLOW_UP_STAGES = frozenset({Stage.MATERIAL_ENTRY, Stage.MATERIAL_SUSTAINED})
STAGE_ORDER = (
    Stage.MATERIAL_ENTRY,
    Stage.MATERIAL_SUSTAINED,
    Stage.MATERIAL_OBSERVING,
    Stage.MATERIAL_FATIGUE,
    Stage.MATERIAL_ELIMINATED,
)
STAGE_LABELS = {
    Stage.MATERIAL_ENTRY: "入场期",
    Stage.MATERIAL_SUSTAINED: "稳定期",
    Stage.MATERIAL_OBSERVING: "待观察",
    Stage.MATERIAL_FATIGUE: "疲劳期",
    Stage.MATERIAL_ELIMINATED: "淘汰期",
}


@dataclass(frozen=True)
class Dataset:
    materials: dict[str, list[MaterialFact]]
    rows: int
    material_count: int
    first_date: date
    last_date: date


@dataclass(frozen=True)
class Evaluation:
    material_id: str
    day: int
    stage: Stage
    good: bool
    holdout: bool
    selected: bool = False
    total_roi: float = 0.0
    roi_cv: float = 0.0
    avg_daily_cost: float = 0.0


@dataclass(frozen=True)
class Metrics:
    eligible: int
    base_rate: float
    selected: int
    coverage: float
    precision: float
    lift: float


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def load_dataset(path: Path) -> Dataset:
    materials: dict[str, list[MaterialFact]] = {}
    rows = 0
    first_date: date | None = None
    last_date: date | None = None
    material_ids: set[str] = set()

    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows += 1
            material_ids.add(row["filename"])
            day = date.fromisoformat(row["date"])
            first_date = day if first_date is None or day < first_date else first_date
            last_date = day if last_date is None or day > last_date else last_date

            spend = _to_float(row["cost"])
            if spend <= 0:
                continue
            materials.setdefault(row["filename"], []).append(
                MaterialFact(
                    date=day,
                    spend=spend,
                    income_order=_to_float(row["d0RechargeAmt"]),
                    income_ad=_to_float(row["d0Iaa"]),
                    impressions=int(_to_float(row["showCnt"])),
                    clicks=int(_to_float(row["clickCnt"])),
                )
            )

    for facts in materials.values():
        facts.sort(key=lambda f: f.date)

    if first_date is None or last_date is None:
        raise ValueError(f"数据为空：{path}")

    return Dataset(
        materials=materials,
        rows=rows,
        material_count=len(material_ids),
        first_date=first_date,
        last_date=last_date,
    )


def without_ad(facts: list[MaterialFact]) -> list[MaterialFact]:
    """充值口径敏感性分析：把 IAA 收入置零"""
    return [replace(f, income_ad=0.0) for f in facts]


def is_holdout(material_id: str) -> bool:
    digest = int(hashlib.sha256(material_id.encode()).hexdigest(), 16)
    return digest % 100 < HOLDOUT_PCT


def future_roi(facts: list[MaterialFact]) -> float:
    cost = sum(f.spend for f in facts)
    return sum(f.income_order + f.income_ad for f in facts) / cost if cost > 0 else 0.0


def evaluate_checkpoint(
    materials: dict[str, list[MaterialFact]],
    day: int,
    detector: MaterialLifecycleDetector,
) -> list[Evaluation]:
    """每个素材只在第 day 个活跃日判一次，只用该日及以前的数据"""
    results: list[Evaluation] = []
    for material_id, facts in materials.items():
        if len(facts) <= day:
            continue
        stage = detector.detect(aggregate_material(facts[:day])).stage
        results.append(
            Evaluation(
                material_id=material_id,
                day=day,
                stage=stage,
                good=future_roi(facts[day:]) >= BREAKEVEN_ROI,
                holdout=is_holdout(material_id),
            )
        )
    return results


def evaluate_first_signal(
    materials: dict[str, list[MaterialFact]],
    detector: MaterialLifecycleDetector,
) -> list[Evaluation]:
    """每个素材取最早一次 FOLLOW_UP 信号，标签用信号日之后的 ROI"""
    results: list[Evaluation] = []
    for material_id, facts in materials.items():
        for day in range(3, len(facts)):
            metrics_snapshot = aggregate_material(facts[:day])
            stage = detector.detect(metrics_snapshot).stage
            if stage in FOLLOW_UP_STAGES:
                verdict = detector.select(stage, metrics_snapshot)
                results.append(
                    Evaluation(
                        material_id=material_id,
                        day=day,
                        stage=stage,
                        good=future_roi(facts[day:]) >= BREAKEVEN_ROI,
                        holdout=is_holdout(material_id),
                        selected=verdict.selected,
                        total_roi=metrics_snapshot.total_roi,
                        roi_cv=metrics_snapshot.roi_cv,
                        avg_daily_cost=metrics_snapshot.avg_daily_cost,
                    )
                )
                break
    return results


def _subset(rows: list[Evaluation], holdout: bool | None) -> list[Evaluation]:
    if holdout is None:
        return rows
    return [r for r in rows if r.holdout is holdout]


def metrics(
    rows: list[Evaluation],
    stage: Stage | None = None,
    eligible_rows: list[Evaluation] | None = None,
    require_selected: bool = False,
) -> Metrics:
    """rows 为选中样本；eligible_rows 为覆盖率/基线的分母（默认同 rows）"""
    population = rows if eligible_rows is None else eligible_rows
    eligible = len(population)
    base_rate = sum(1 for r in population if r.good) / eligible if eligible else 0.0
    selected = [
        r
        for r in rows
        if (
            r.selected
            if require_selected
            else (r.stage == stage if stage is not None else r.stage in FOLLOW_UP_STAGES)
        )
    ]
    count = len(selected)
    precision = sum(1 for r in selected if r.good) / count if count else 0.0
    return Metrics(
        eligible=eligible,
        base_rate=base_rate,
        selected=count,
        coverage=count / eligible if eligible else 0.0,
        precision=precision,
        lift=precision / base_rate if base_rate else 0.0,
    )


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _num(value: float) -> str:
    return f"{value:.2f}x"


def _stage_table(rows: list[Evaluation], holdout: bool | None) -> list[str]:
    subset = _subset(rows, holdout)
    out = [
        "| 阶段 | 样本数 | 覆盖率 | 精确率 | 相对基线 |",
        "|---|---|---|---|---|",
    ]
    for stage in STAGE_ORDER:
        m = metrics(subset, stage)
        if m.selected == 0:
            continue
        out.append(
            f"| {STAGE_LABELS[stage]} | {m.selected} | {_pct(m.coverage)} | "
            f"{_pct(m.precision)} | {_num(m.lift)} |"
        )
    overall = metrics(subset)
    out.append("")
    out.append(f"基线未来达标率：{_pct(overall.base_rate)}（样本 {overall.eligible}）")
    return out


def _signal_summary(
    signals: list[Evaluation],
    population: list[Evaluation],
    holdout: bool | None,
    require_selected: bool = False,
) -> Metrics:
    """首次信号指标：分母用 day3 可判定素材（覆盖率 / 基线）"""
    return metrics(
        _subset(signals, holdout),
        eligible_rows=_subset(population, holdout),
        require_selected=require_selected,
    )


def _gate_breakdown(signals: list[Evaluation]) -> list[str]:
    """A 方案闸门的逐级淘汰统计（按 ROI → 波动 → 消耗 顺序）"""
    limits = MaterialThresholds()
    counts = {"原始信号": len(signals), "ROI不足": 0, "波动过大": 0, "消耗不足": 0, "通过": 0}
    for row in signals:
        if row.total_roi <= limits.MIN_TOTAL_ROI:
            counts["ROI不足"] += 1
        elif row.roi_cv > limits.MAX_ROI_CV:
            counts["波动过大"] += 1
        elif row.avg_daily_cost < limits.MIN_AVG_DAILY_COST:
            counts["消耗不足"] += 1
        else:
            counts["通过"] += 1
    return [
        "| 闸门 | 信号数 |",
        "|---|---|",
        *[f"| {name} | {count} |" for name, count in counts.items()],
    ]


def _sensitivity_table(
    combined: dict[int, list[Evaluation]],
    recharge: dict[int, list[Evaluation]],
) -> list[str]:
    out = [
        "| 口径 | 观测点 | 入选数 | 覆盖率 | 精确率 | 相对基线 |",
        "|---|---|---|---|---|---|",
    ]
    for label, data in (("合并口径", combined), ("充值口径", recharge)):
        for day, rows in data.items():
            m = metrics(rows)
            out.append(
                f"| {label} | day {day} | {m.selected} | {_pct(m.coverage)} | "
                f"{_pct(m.precision)} | {_num(m.lift)} |"
            )
    return out


def build_report(
    dataset: Dataset,
    combined: dict[int, list[Evaluation]],
    recharge: dict[int, list[Evaluation]],
    data_path: Path,
) -> str:
    detector = MaterialLifecycleDetector()
    first_signal = evaluate_first_signal(dataset.materials, detector)
    first_signal_recharge = evaluate_first_signal(
        {k: without_ad(v) for k, v in dataset.materials.items()}, detector
    )

    lines = [
        "# 素材选择策略回测报告",
        "",
        "## 数据与口径",
        "",
        f"- 数据源：`{data_path}`",
        f"- 时间范围：{dataset.first_date} ~ {dataset.last_date}",
        f"- 总行数：{dataset.rows}，素材数：{dataset.material_count}，有消耗素材数：{len(dataset.materials)}",
        "- 活跃日 = 当日消耗 > 0；零消耗日不进入 ROI 序列",
        "- ROI = (订单充值 + IAA 广告分成) / 消耗",
        "- 标签 = 观测点之后活跃日的累计 ROI >= 40%",
        f"- 切分：material_id SHA-256 哈希，{100 - HOLDOUT_PCT}% 校准 / {HOLDOUT_PCT}% 留出，素材不跨集",
        "",
        "## 观测点判定",
        "",
    ]

    for day in CHECKPOINTS:
        lines.extend([f"### Day {day}（校准集 + 留出集）", ""])
        lines.extend(_stage_table(combined[day], None))
        lines.extend(["", f"### Day {day}（留出集）", ""])
        lines.extend(_stage_table(combined[day], True))
        lines.append("")

    first_signal_population = combined[3]
    first_signal_recharge_population = recharge[3]
    lines.extend(
        [
            "## 选品闸门（A 方案）",
            "",
            "在首次 ENTRY / SUSTAINED 信号之上叠加三道闸门，按顺序判定：",
            "",
            "1. 累计 ROI > 50%（盈利线之上的选品余量）",
            "2. ROI 波动率 <= 0.50（过滤一日冲高）",
            "3. 日均消耗 >= 200（已被系统放量验证）",
            "",
            "### 闸门逐级淘汰（全集）",
            "",
        ]
    )
    lines.extend(_gate_breakdown(first_signal))
    lines.extend(["", "### 闸门后的首次信号", ""])
    for title, holdout in (("全集", None), ("校准集", False), ("留出集", True)):
        m = _signal_summary(first_signal, first_signal_population, holdout, require_selected=True)
        lines.append(
            f"- {title}：入选 {m.selected} 条，覆盖 {_pct(m.coverage)}，"
            f"精确率 {_pct(m.precision)}，相对基线 {_num(m.lift)}（基线 {_pct(m.base_rate)}）"
        )

    lines.extend(
        [
            "",
            "### 对照：未加闸门的原始阶段信号",
            "",
        ]
    )
    for title, holdout in (("全集", None), ("校准集", False), ("留出集", True)):
        m = _signal_summary(first_signal, first_signal_population, holdout)
        lines.append(
            f"- {title}：入选 {m.selected} 条，覆盖 {_pct(m.coverage)}，"
            f"精确率 {_pct(m.precision)}，相对基线 {_num(m.lift)}（基线 {_pct(m.base_rate)}）"
        )

    lines.extend(["", "## 口径敏感性（合并口径 vs 充值口径）", ""])
    lines.extend(_sensitivity_table(combined, recharge))
    lines.extend(
        [
            "",
            "## 首次信号的充值口径对照",
            "",
        ]
    )
    for title, holdout in (("全集", None), ("留出集", True)):
        raw = _signal_summary(first_signal_recharge, first_signal_recharge_population, holdout)
        gated = _signal_summary(
            first_signal_recharge, first_signal_recharge_population, holdout, require_selected=True
        )
        lines.append(
            f"- {title} · 原始阶段信号：入选 {raw.selected} 条，覆盖 {_pct(raw.coverage)}，"
            f"精确率 {_pct(raw.precision)}，相对基线 {_num(raw.lift)}（基线 {_pct(raw.base_rate)}）"
        )
        lines.append(
            f"- {title} · A 方案闸门后：入选 {gated.selected} 条，覆盖 {_pct(gated.coverage)}，"
            f"精确率 {_pct(gated.precision)}，相对基线 {_num(gated.lift)}（基线 {_pct(gated.base_rate)}）"
        )

    holdout_signal = _signal_summary(
        first_signal, first_signal_population, True, require_selected=True
    )
    passed = (
        holdout_signal.lift >= 3.0
        and holdout_signal.precision >= 0.70
        and holdout_signal.coverage >= 0.02
    )
    lines.extend(
        [
            "",
            "## 验收结论（A 方案）",
            "",
            f"- 留出集精确率 = {_pct(holdout_signal.precision)}（目标 >= 70%）："
            f"{'通过' if holdout_signal.precision >= 0.70 else '未通过'}",
            f"- 留出集 lift = {_num(holdout_signal.lift)}（目标 >= 3.0x）："
            f"{'通过' if holdout_signal.lift >= 3.0 else '未通过'}",
            f"- 覆盖率 = {_pct(holdout_signal.coverage)}（目标 >= 2%）："
            f"{'通过' if holdout_signal.coverage >= 0.02 else '未通过'}",
            f"- 总体：{'通过' if passed else '未通过'}",
            "",
            "## 风险与口径说明",
            "",
            "- 幸存者偏差：停投素材从数据消失，未来 ROI 只观测到存活者，标签偏乐观。",
            f"- 单窗口数据（{dataset.first_date} ~ {dataset.last_date}），未验证时间漂移。",
            "- 合并口径把基线未来达标率整体抬高；40% 线在该口径下的业务含义需按 PRD §6.3 待定决策复核。",
            "- 日均消耗是“系统已经放量”的显性信号，选出来的是已被验证的素材，不是被低估的素材；",
            "  若目标是发现未放量素材，应改用不依赖消耗的质量闸门，精确率会下降。",
            "- 标签是现有投放下的未来 ROI，不等于新建放量任务的增量 ROI。",
            "- 按需求不引入 LightGBM，因此不与 short-drama-scoring 的模型分数做效果对比。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="素材选择策略回测")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="素材日级 CSV 路径")
    args = parser.parse_args()

    dataset = load_dataset(args.data)
    detector = MaterialLifecycleDetector()
    combined = {day: evaluate_checkpoint(dataset.materials, day, detector) for day in CHECKPOINTS}
    recharge_materials = {k: without_ad(v) for k, v in dataset.materials.items()}
    recharge = {day: evaluate_checkpoint(recharge_materials, day, detector) for day in CHECKPOINTS}

    report = build_report(dataset, combined, recharge, args.data)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
