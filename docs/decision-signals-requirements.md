# 决策信号与决策日志需求
## 一、背景与范围
信号体系从 v1.0 的单一 `FOLLOW_UP` 扩展为 `FOLLOW_UP` + `ELIMINATE` 双向信号。
素材维度选品目前处于策略验证与原型展示阶段：已完成生命周期规则、A 方案三道选品闸门和离线回测，用于验证选品规则与前端展示形态。
本期范围：
- 产品：新增 `ELIMINATE` 淘汰信号；新增素材信号口径
---
## 二、信号体系总览
| 信号 | 业务语义 | 目标维度 | 下游动作 |
|---|---|---|---|
| `FOLLOW_UP` | 目标值得继续投放 | product / campaign / material | 新建放量任务 |
| `ELIMINATE` | 目标已不值得投放 | product | 停止投放并移除任务 |
两类信号共用 `BuildSignal` 字段契约，字段结构完全一致，仅 `signal_type` 不同。
冷却键为 `(目标, 信号类型)`，`FOLLOW_UP` 与 `ELIMINATE` 各自独立冷却，互不抑制。
下游按 `(target_dimension, target_id, signal_type)` 幂等；`signal_id` 含生成时间戳，仅用于追踪，不作为下游幂等键。
---
## 三、ELIMINATE 淘汰信号
### 3.1 目标与非目标
**目标**：
- 新增 `ELIMINATE`，覆盖短剧维度的退出期与衰退期
- 信号到达下游后，停止该短剧的自动化投放并移除任务
- 淘汰后若 ROI 回升，允许重新跟投入池
**非目标**：
- Campaign / 素材维度的淘汰本期不做
- 本系统不执行停投、删任务等动作，只输出信号
- 不做本地去重，由下游按目标维度幂等处理
### 3.2 触发口径
触发阶段取现有短剧生命周期判定结果，不新增判定规则：
| 阶段 | 置信度 |
|---|---|
| `product_exit` | 0.85 |
| `product_decline` | 0.80 |
两个阶段纳入可配置的淘汰阶段范围，可调整；与跟投阶段不得有交集。
### 3.3 重入策略
允许重入跟投名单，淘汰不写持久化黑名单：
- 淘汰后若阶段回升到 `product_entry` / `product_growth` / `product_sustained`，`FOLLOW_UP` 照常产出，下游重新建任务
- `FOLLOW_UP` 与 `ELIMINATE` 各自独立冷却，冷却键为（目标，信号类型），互不抑制
- 下游按目标最后一条信号理解当前状态：先 `ELIMINATE` 后 `FOLLOW_UP` 表示重新入池
### 3.4 幂等与去重
本系统不做跨进程去重，重复运行 pipeline 可能重复产出同一信号。下游按 `(target_dimension, target_id, signal_type)` 幂等：
- 已在池内的目标重复收到 `ELIMINATE` 时不重复执行移除
- 池外目标收到 `ELIMINATE` 时按空操作处理
### 3.5 不要求先有跟投
`ELIMINATE` 按阶段无条件产出，不检查目标是否曾收到 `FOLLOW_UP`、是否在自动化池内。
原因：系统不维护投放状态；若以「曾跟投」为前提，需额外持久化状态；且短剧停投后数据源不可见。
### 3.6 字段契约
复用 `BuildSignal`，仅 `signal_type` 新增枚举值：
| 字段 | 淘汰信号取值 |
|---|---|
| `signal_id` | `YYYYMMDDHHMMSS_目标ID`，含生成时间戳，仅用于追踪 |
| `signal_type` | `ELIMINATE` |
| `target_dimension` | `product` |
| `target_id` | 短剧视频 ID |
| `language_code` | 透传 |
| `script_no` | 透传剧本编号 |
| `shortplay_name` | 透传短剧名 |
| `reason` | 生命周期判定理由 |
| `confidence` | 阶段判定置信度，非淘汰概率 |
| `timestamp` | 信号生成时间（UTC） |
### 3.7 配置
信号配置需要支持：
| 配置项 | 默认值 | 说明 |
|---|---|---|
| 淘汰阶段 | product_exit / product_decline | 产出 `ELIMINATE` 的阶段，可调整 |
跟投阶段与淘汰阶段不得重叠；重叠时配置不生效并提示。
---
## 四、素材维度 FOLLOW_UP
### 4.1 现状
素材选品：已完成生命周期规则、A 方案三道选品闸门和离线回测。
### 4.2 选品口径
- 阶段为 `material_entry` 或 `material_sustained`
- 且通过 A 方案三道闸门：累计 ROI > 50%、ROI 波动率 <= 0.50、日均消耗 >= 200
- 三关全过才产 `FOLLOW_UP(material)`
#### 4.2.1 数据需求
| 类别 | 字段 | 要求 |
|---|---|---|
| 主体 | material_id | 稳定唯一，素材 filename |
| 时间 | date | 素材 × 自然日，每天一行 |
| 归属 | language_code / script_no / shortplay_name | 信号分流与展示必需 |
| 消耗 | spend | number ≥ 0，当日消耗 |
| 收入 | income_order / income_ad | number ≥ 0，订单充值 / IAA 分成 |
| 流量 | impressions / clicks | number ≥ 0，用于 CTR 与疲劳判定 |
| 可选 | active_cnt、所属短剧 ID | 诊断辅助 |

- 覆盖：当日有消耗的全部素材，非 TopN；每个素材提供从首投到昨日的完整历史，零消耗日显式 0
- 最少历史：首判 2 个活跃日；持续判定 5 个活跃日；建议保留 14 天
- 质量：数值型、无 null、币种 / 时区统一；不供 ROI / CTR 等派生指标；日更，凌晨 2 点前到达
- 量级：约 1.4 万素材，日增约 3 千条有消耗记录
- 派生指标：ROI、活跃日、近 2/3/5 日 ROI、ROI 波动率、日均消耗、CTR 均由本系统计算
#### 4.2.2 首判时点
素材在第 2 个活跃日开始判定；第 1 个活跃日只观察。留出集单票判定对比：

| 首判时点 | 入选数 | 覆盖率 | 精确率 |
|---|---|---|---|
| 第 1 个活跃日 | 28 | 1.1% | 57.1% |
| 第 2 个活跃日 | 51 | 2.9% | 78.4% |
| 第 3 个活跃日 | 39 | 3.5% | 74.4% |

第 1 天样本少、波动大，不采用；第 2 天相比第 3 天提前 1 天且精确率不降。第 2 天早期 / 后期窗口精确率 86.7% / 75.0%。留出集样本量较小（51 / 39），上线前需扩大样本复核。
上表是各时点的单票 cohort；第 2 天未通过的素材仍可在后续活跃日再次判定。
#### 4.2.3 判定逻辑
活跃日 = 当日消耗 > 0 的自然日。

| 活跃日 | 条件 | 阶段 | 是否进入选品 |
|---|---|---|---|
| < 2 | 时间不足 | `material_observing` | 否 |
| 2-4 | 累计 ROI < 10% | `material_eliminated` | 否 |
| 2-4 | 累计 ROI > 40% 且近 2 日消耗占比 >= 50% | `material_entry` | 是 |
| 2-4 | 其他 | `material_observing` | 否 |
| >= 5 | 近 3 日 ROI < 10% | `material_eliminated` | 否 |
| >= 5 | 曾达标且（近 2 日 ROI 较峰值降 > 50% 或近 2 日 CTR 较前 3 日降 > 20%） | `material_fatigue` | 否 |
| >= 5 | 近 3 日 ROI > 40% 且近 2 日 ROI 均值 >= 30% 且近 2 日消耗占比 >= 50% | `material_sustained` | 是 |
| >= 5 | 其他 | `material_observing` | 否 |
#### 4.2.4 产出逻辑
只有 `material_entry` / `material_sustained` 进入选品，按顺序通过三道闸门：

| 顺序 | 闸门 | 阈值 | 含义 |
|---|---|---|---|
| 1 | 累计 ROI | > 50% | 盈利线之上的选品余量 |
| 2 | ROI 波动率 | <= 0.50 | 过滤一日冲高 |
| 3 | 日均消耗 | >= 200 | 已被放量验证 |

三关全过才产 `FOLLOW_UP(material)`，字段见 4.3。
- 冷却：默认 24 小时，按 `(material_id, FOLLOW_UP)` 计
- 幂等：下游按 `(target_dimension, target_id, signal_type)` 去重
- 重入：阶段回升到入场期 / 稳定期且闸门再次通过，冷却期后可重新产出
- 信号不带 scale，放量规模由下游模板承载
### 4.3 展示字段
沿用 `BuildSignal` 标准字段，不新增闸门指标字段：
| 字段 | 素材取值 |
|---|---|
| `signal_type` | `FOLLOW_UP` |
| `target_dimension` | `material` |
| `target_id` | 素材 filename |
| `language_code` | 素材语言 |
| `script_no` | 剧本编号 |
| `shortplay_name` | 所属短剧名 |
| `reason` | 选品通过原因，文本内可带闸门数值 |
| `confidence` | 生命周期阶段判定置信度 |
| `timestamp` | 信号生成时间 |
### 4.4 mock 数据
决策日志新增 4 条素材 mock 信号，覆盖英语 / 韩语 / 阿拉伯语 / 西班牙语，`reason` 形如：
`选品通过: 累计ROI=68.4% > 50%，波动率=0.23 ≤ 0.50，日均消耗=412.0 ≥ 200`
---
## 五、原型改动
### 5.1 Dashboard
- 概览卡片改为 6 张：短剧总数、活跃广告、活跃素材、今日信号、跟投信号、淘汰信号
- 生命周期分布增加「素材」维度，展示 `material_observing` / `material_entry` / `material_sustained` / `material_fatigue` / `material_eliminated` 5 个阶段
- 今日信号类型分布同时展示 `FOLLOW_UP` 与 `ELIMINATE`
- 今日信号摘要同时展示跟投信号与淘汰信号
### 5.2 Decisions
- 信号类型筛选：跟投信号 / 淘汰信号
- 目标维度筛选：短剧 / 广告单元 / 素材
- 两个筛选可组合；任一筛选变化回到第 1 页
- 维度列支持「素材」标签
- 详情抽屉保持原始 JSON，不展示结构化闸门字段
### 5.3 Config
- 每阶段在「跟投（FOLLOW_UP）/ 淘汰（ELIMINATE）/ 不产出」之间三选一
- 阶段列表覆盖短剧 / 广告单元 / 素材；`material_entry` / `material_sustained` 默认跟投，其余不产出
- 素材阶段已纳入配置范围，正式信号下发另行评审
- 同一阶段只能二选一；跟投阶段与淘汰阶段不得有交集
- 冷却时长按阶段独立配置；选择「不产出」时冷却输入禁用
- 本页仍为前端示例数据，保存仅作用于当前页面
---
## 六、验收标准
| 项 | 标准 |
|---|---|
| ELIMINATE 触发 | `product_exit` / `product_decline` 产出 `ELIMINATE`，其余阶段不产出 |
| 阶段交集 | 跟投阶段与淘汰阶段有交集时，配置不生效并提示 |
| 冷却独立 | 同一目标的 `FOLLOW_UP` 与 `ELIMINATE` 冷却互不影响 |
| Dashboard | 6 张概览卡片（含活跃素材）；生命周期分布含素材；类型分布与摘要包含淘汰信号 |
| Decisions | 信号类型与目标维度可组合筛选；素材标签、空态正常 |
| Config | 阶段列表覆盖短剧 / 广告单元 / 素材；每阶段可在跟投 / 淘汰 / 不产出之间选择 |
| 素材展示 | 决策日志展示 4 条素材示例信号，详情含素材维度信息 |
| 回归 | 原有短剧 / 广告单元信号展示与筛选不变 |
| 原型验收 | 三页原型可完整演示上述行为，筛选、空态、详情均正常 |
