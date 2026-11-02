# 淘汰信号需求（v4.1 增量需求）
> 本文已被 `docs/decision-signals-requirements.md` 取代，仅保留作历史记录。
本文是 PRD 之后的增量需求文档，描述新增的 `ELIMINATE` 淘汰信号。PRD.md 保持原样，本次改动不回写。
## 一、背景
短剧进入自动化投放任务后，任务本身没有失效机制：一旦由 `FOLLOW_UP` 跟投入池，即使生命周期已进入衰退或退出阶段，下游仍会持续投放，消耗无法自动止损。
现有信号体系只覆盖「值得继续投」的方向，缺少反向的「停止投放并移除任务」出口。
---
## 二、目标与非目标
**目标**：
- 新增 `ELIMINATE` 淘汰信号，覆盖短剧维度的退出期与衰退期
- 信号到达下游后，停止该短剧的自动化投放并移除任务
- 淘汰后若 ROI 回升，允许重新跟投入池
**非目标**：
- Campaign / 素材维度的淘汰本期不做
- 本系统不执行停投、删任务等动作，只输出信号
- 不做本地去重，由下游按目标维度幂等处理
---
## 三、信号定义
| 项 | 内容 |
|---|---|
| 信号类型 | `ELIMINATE` |
| 目标维度 | `product`（短剧） |
| 业务语义 | 目标已不再值得投放，应停止并移出自动化投放 |
| 下游动作 | 停止该短剧的自动化投放，并从自动化任务池移除 |
| 触发时机 | 生命周期阶段进入 `product_exit` 或 `product_decline` |
---
## 四、触发口径
触发阶段取现有短剧生命周期判定结果，不新增判定规则：

| 阶段 | 判定条件 | 置信度 |
|---|---|---|
| `product_exit` | 3-7天 / 7-14天：近3天 ROI 均值 < 10%；>14天：ROI < 10% 持续5天 | 0.85 |
| `product_decline` | 前后半段 ROI 均值跌幅 > 30% | 0.80 |

两个阶段由 `config/signal_rules.json` 的 `eliminate_stages` 注入，可调整；与 `follow_up_stages` 不得有交集。
---
## 五、重入策略
允许重入，淘汰不写持久化黑名单：
- 淘汰后若阶段回升到 `product_entry` / `product_growth` / `product_sustained`，`FOLLOW_UP` 照常产出，下游重新建任务
- `FOLLOW_UP` 与 `ELIMINATE` 各自独立冷却，冷却键为（目标，信号类型），互不抑制
- 下游按目标最后一条信号理解当前状态：先 `ELIMINATE` 后 `FOLLOW_UP` 表示重新入池
---
## 六、幂等与去重
本系统不做跨进程去重，重复运行 pipeline 可能重复产出同一信号。下游按 `(target_dimension, target_id, signal_type)` 幂等：
- 已在池内的目标重复收到 `ELIMINATE` 时不重复执行移除
- 池外目标收到 `ELIMINATE` 时按空操作处理
`signal_id` 含生成时间戳，不稳定，不作为下游幂等键；PRD §5.3.3 中「以 signal_id 为幂等键」的表述以本文为准。
---
## 七、不要求先有跟投
`ELIMINATE` 按阶段无条件产出，不检查目标是否曾收到 `FOLLOW_UP`、是否在自动化池内。
原因：系统不维护投放状态。若以「曾跟投」为前提，需额外持久化状态；且短剧停投后数据源不可见（见第九节）。
---
## 八、字段契约
复用现有 `BuildSignal`，仅 `signal_type` 新增枚举值：

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

信号不带 scale，字段结构与 `FOLLOW_UP` 完全一致。
---
## 九、已知限制
数据源 `data/video_daily/*.json` 是每日按消耗 Top50 抽样：
- 短剧停投后从表中消失，系统无法观测「它已停投」，只能淘汰仍在投但表现差的目标
- 停投与漏数不可区分，不能以「表中消失」作为淘汰依据
- PRD §6.3 的全量有消耗口径上线前，淘汰覆盖面天然不完整
---
## 十、配置
`config/signal_rules.json` 新增字段：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `eliminate_stages` | `["product_exit", "product_decline"]` | 产出 `ELIMINATE` 的阶段，须为合法 Stage |

`follow_up_stages` 与 `eliminate_stages` 交集校验失败时，配置加载直接报错。
---
## 十一、验收标准
- `product_exit` / `product_decline` 阶段产出 `ELIMINATE`，其余阶段不产出
- `follow_up_stages` 与 `eliminate_stages` 有交集时，构造 mapper 与加载配置均报错
- 同一目标的 `FOLLOW_UP` 与 `ELIMINATE` 冷却互不影响
- 前端原型：决策日志支持按「淘汰信号」筛选并以红色 tag 展示；看板类型分布与摘要包含淘汰；信号配置页支持每阶段在跟投 / 淘汰 / 不产出之间选择
- `uv run python run_pipeline.py` 输出中出现 `ELIMINATE`，阶段分布与信号数量一致
- `uv run pytest` 全绿
---
## 十二、与 PRD 的关系
本文是 PRD 的增量需求。自本需求起，新增需求统一写入 `docs/` 下的独立文档，不回写 PRD.md。
PRD.md 中「本期唯一输出 FOLLOW_UP」等表述对 v4.0 仍然有效，v4.1 起以本文为准。
