# 生命周期阈值验证报告

## 数据来源

| 数据集 | 时间范围 | 商品数 | Campaign数 |
|--------|----------|--------|------------|
| 0301-0307 | 2026-03-01 ~ 2026-03-07 | 1,944 | 109,198 |
| 0315-0321 | 2026-03-15 ~ 2026-03-21 | 2,447 | 119,392 |

## 商品（短剧）维度

### 阶段分布（跨数据集验证）

| 阶段 | 0301-0307 | 0315-0321 | 结论 |
|------|-----------|-----------|------|
| 冷启动失败 | 19.7% | 22.1% | 一致 (~20%) |
| 成长期 | 5.3% | 7.2% | 一致 (5-7%) |
| 成熟期 | 5.9% | 7.4% | 一致 (6-8%) |
| 衰退期 | 69.0% | 63.3% | 一致 (~65%) |

### 核心发现

1. **首日成本决定冷启动风险**

| 首日消耗 | 冷启动率 (0301) | 冷启动率 (0315) |
|----------|-----------------|-----------------|
| < 50元 | 32.2% | 32.5% | **完全一致** |
| < 100元 | 29.5% | 31.1% | 一致 |
| < 200元 | 27.1% | 29.7% | 一致 |
| >= 500元 | **< 5%** | **< 5%** | **高度一致** |

2. **CTR 2-3% 是最佳区间**

| CTR阈值 | 成功率 (0301) | 成功率 (0315) |
|---------|---------------|---------------|
| >= 1% | 81.8% | 76.2% |
| >= 2% | **83.2%** | **77.8%** | ← 峰值 |
| >= 3% | 83.1% | 78.4% |
| >= 5% | 78.0% | 74.0% | ← 反降 |

### 最终阈值配置

```python
ProductThresholds:
    COLD_START_DURATION_HOURS = 24
    COST_CRITICAL = 50        # < 50元 冷启动率 32%
    COST_HEALTHY = 500        # >= 500元 冷启动率 < 5%
    COST_FIRST_24H_THRESHOLD = 100  # 关键门槛

    GROWTH_COST_CHANGE_MIN = 0.20    # +20%
    MATURE_COST_CHANGE_RANGE = (-0.20, 0.20)
    DECAY_COST_CHANGE_MAX = -0.30    # -30%
    DECAY_CONSECUTIVE_HOURS = 3      # 连续3天

    CTR_GOLDEN_RANGE = (0.02, 0.05)  # 2-5%
    CTR_HIGH_RISK = 0.06             # > 6% 风险
```

---

## 广告单元（Campaign）维度

### 阶段分布

| 阶段 | 0301-0307 | 0315-0321 |
|------|-----------|-----------|
| 冷死亡 (cold_dead) | 61.4% | 65.7% |
| 冷启动 (cold_start) | 5.1% | 4.1% |
| 增长期 (growth) | 8.1% | 10.2% |
| 稳定期 (stable) | 10.9% | 10.0% |
| 衰退期 (decay) | 14.6% | 10.0% |

### 核心发现

1. **Campaign 死亡率极高（60%+）**，远高于商品的 20%
2. **首日消耗 >= 200元** 存活率显著更高
3. **极低预算(<10元)反而存活率略高**，可能是测试素材

### 最终阈值配置

```python
CampaignThresholds:
    COLD_START_DURATION_HOURS = 24
    COST_CRITICAL = 50        # < 50元 死亡率高
    COST_HEALTHY = 200        # >= 200元 存活率更高

    STABLE_COST_CHANGE_RANGE = (-0.30, 0.30)
    DECAY_COST_DROP_MIN = 0.30
    DECAY_CONSECUTIVE_HOURS = 12  # 连续12小时

    SHUTDOWN_COST_PER_HOUR_MAX = 1.0  # 每小时<1元
    SHUTDOWN_DURATION_MIN = 48
```

---

## 判定逻辑

### 商品判定流程

```
1. duration <= 24h AND cost < 50 → PRODUCT_COLD_START (冷启动失败)
2. duration > 24h AND cost_change > +20% → PRODUCT_GROWTH (成长期)
3. cost_change < -30% → PRODUCT_DECLINE (衰退期)
4. -20% <= cost_change <= +20% AND cost >= 200 → PRODUCT_MATURE (成熟期)
5. 其他 → PRODUCT_INTRODUCING (引入期)
```

### Campaign 判定流程

```
1. duration <= 24h AND cost < 50 → CAMPAIGN_COLD_DEAD (冷死亡)
2. duration <= 24h → CAMPAIGN_COLD_START (冷启动)
3. cost_per_hour < 1 AND duration > 48h → CAMPAIGN_SHUTDOWN (关停期)
4. cost_change < -30% → CAMPAIGN_DECAY (衰退期)
5. cost_change > +20% → CAMPAIGN_GROWTH (增长期)
6. 其他 → CAMPAIGN_STABLE (稳定期)
```

---

## 待验证

1. **素材维度** - 当前数据中没有素材ID，无法验证
2. **连续天数判定** - 建议加入连续3天条件防抖动
3. **季节性因素** - 两周数据结论接近，但可能存在季节性差异
