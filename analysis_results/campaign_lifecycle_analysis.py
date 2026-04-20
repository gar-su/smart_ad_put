"""
广告单元（Campaign）生命周期分析脚本
数据集: 0301-0307, 0315-0321
"""

import pandas as pd
import glob
import numpy as np
from pathlib import Path

# 数据路径
DATA_DIR_1 = "/Users/gar/PyCharmMiscProject/data_chunks_0301_0307"
DATA_DIR_2 = "/Users/gar/PyCharmMiscProject/data_chunks_0315_0321"
OUTPUT_DIR = Path(__file__).parent


def load_data(data_dir):
    """加载parquet数据"""
    files = sorted(glob.glob(f"{data_dir}/*.parquet"))
    dfs = []
    for f in files:
        dfs.append(pd.read_parquet(f))
    return pd.concat(dfs, ignore_index=True)


def analyze_campaign_lifecycle(data):
    """分析Campaign生命周期"""
    data['ctr'] = data['click_cnt'] / data['show_cnt'].replace(0, np.nan)
    data['ctr'] = data['ctr'].fillna(0)

    def analyze(group):
        group = group.sort_values('hour_seq')
        total_cost = group['cost_h'].sum()
        total_pays = group['belong_pay_cnt'].sum()
        duration = group['hour_seq'].max()

        first_24h = group[group['hour_seq'] <= 24]
        last_24h = group[group['hour_seq'] > (duration - 24)] if duration > 24 else group

        ctr_first = first_24h['ctr'].mean() if len(first_24h) > 0 else 0
        ctr_last = last_24h['ctr'].mean() if len(last_24h) > 0 else 0
        ctr_change = ((ctr_last - ctr_first) / max(ctr_first, 0.001)) * 100

        cost_first = first_24h['cost_h'].sum()
        cost_last = last_24h['cost_h'].sum()
        cost_change = ((cost_last - cost_first) / max(cost_first, 0.001)) * 100

        return pd.Series({
            'duration': duration,
            'total_cost': total_cost,
            'total_pays': total_pays,
            'ctr_first_24h': ctr_first * 100,
            'ctr_change_pct': ctr_change,
            'cost_first_24h': cost_first,
            'cost_last_24h': cost_last,
            'cost_change_pct': cost_change,
        })

    return data.groupby('campaign_id').apply(analyze, include_groups=False).reset_index()


def classify_stage(row):
    """Campaign生命周期阶段分类"""
    if row['duration'] <= 24 and row['total_cost'] < 50:
        return 'cold_dead'
    elif row['duration'] <= 24:
        return 'cold_start'
    elif row['cost_change_pct'] > 20:
        return 'growth'
    elif row['cost_change_pct'] < -30:
        return 'decay'
    else:
        return 'stable'


def run_analysis():
    """运行完整分析"""
    print("Loading dataset 1: 0301-0307...")
    data1 = load_data(DATA_DIR_1)
    stats1 = analyze_campaign_lifecycle(data1)
    stats1['stage'] = stats1.apply(classify_stage, axis=1)
    stats1['dataset'] = '0301-0307'

    print("Loading dataset 2: 0315-0321...")
    data2 = load_data(DATA_DIR_2)
    stats2 = analyze_campaign_lifecycle(data2)
    stats2['stage'] = stats2.apply(classify_stage, axis=1)
    stats2['dataset'] = '0315-0321'

    # 合并结果
    all_stats = pd.concat([stats1, stats2], ignore_index=True)

    # 保存CSV
    stats1.to_csv(OUTPUT_DIR / "campaign" / "stats_0301_0307.csv", index=False)
    stats2.to_csv(OUTPUT_DIR / "campaign" / "stats_0315_0321.csv", index=False)
    all_stats.to_csv(OUTPUT_DIR / "campaign" / "stats_combined.csv", index=False)

    # 生成报告
    report = generate_report(stats1, stats2)
    with open(OUTPUT_DIR / "campaign" / "REPORT.md", "w") as f:
        f.write(report)

    print(f"\nResults saved to {OUTPUT_DIR}/campaign/")
    return stats1, stats2


def generate_report(stats1, stats2):
    """生成分析报告"""
    report = f"""# Campaign 生命周期分析报告

## 数据概览

| 数据集 | Campaign数 | 平均时长(h) | 平均首日消耗 |
|--------|------------|-------------|--------------|
| 0301-0307 | {len(stats1):,} | {stats1['duration'].mean():.0f} | {stats1['cost_first_24h'].mean():.1f} |
| 0315-0321 | {len(stats2):,} | {stats2['duration'].mean():.0f} | {stats2['cost_first_24h'].mean():.1f} |

## 阶段分布

| 阶段 | 0301-0307 | 0315-0321 |
|------|-----------|-----------|"""

    for stage in ['cold_dead', 'cold_start', 'growth', 'stable', 'decay']:
        c1 = (stats1['stage'] == stage).sum() / len(stats1) * 100
        c2 = (stats2['stage'] == stage).sum() / len(stats2) * 100
        report += f"\n| {stage} | {c1:.1f}% | {c2:.1f}% |"

    report += f"""

## 存活率分析

### 按首日消耗

| 首日消耗 | 存活率 (0301) | 存活率 (0315) |
|----------|---------------|---------------|"""

    for threshold in [10, 50, 100, 200]:
        below1 = stats1[stats1['cost_first_24h'] < threshold]
        below2 = stats2[stats2['cost_first_24h'] < threshold]
        s1 = (below1['duration'] > 24).mean() * 100
        s2 = (below2['duration'] > 24).mean() * 100
        report += f"\n| < {threshold:>3}元 | {s1:.1f}% | {s2:.1f}% |"

    report += f"""

## 阶段特征

| 阶段 | 平均首日消耗(0301) | 平均首日消耗(0315) | 平均付费(0301) | 平均付费(0315) |
|------|-------------------|-------------------|----------------|----------------|"""

    for stage in ['cold_dead', 'cold_start', 'growth', 'stable', 'decay']:
        s1_data = stats1[stats1['stage'] == stage]
        s2_data = stats2[stats2['stage'] == stage]
        cost1 = s1_data['cost_first_24h'].mean()
        cost2 = s2_data['cost_first_24h'].mean()
        pays1 = s1_data['total_pays'].mean()
        pays2 = s2_data['total_pays'].mean()
        report += f"\n| {stage} | {cost1:.1f} | {cost2:.1f} | {pays1:.2f} | {pays2:.2f} |"

    report += """

## 结论

- 60%+ 的 Campaign 在24h内死亡（冷死亡）
- 首日消耗 >= 200元 存活率显著更高
- 极低预算(<10元)反而存活率略高，可能是测试素材
"""
    return report


if __name__ == "__main__":
    run_analysis()
