# 数据需求单 · 诊断服务数据供给契约（草案 v1.1）
> **状态**：单列待整合。本份数据需求按最新口径单列成文，**尚未并入 PRD**；后续整体整合 PRD 时提醒纳入数据供给相关章节。
> **定稿需核对**：末尾「开放校验点」两条，属业务决策，整合 PRD 前须有结论。
> **v1.1 变更**：新增 campaign 维度小时级供给（诊断服务 campaign 判定所需）。
## 1. 定位与原则
大数据侧只供原子事实（钱、量、身份属性），不供任何派生指标。
派生指标（ROI / CTR / CPC / CPM / ARPU / 环比 / 达标率…）一律不在供给中出现，由本系统派生层计算。
收益约定：新增特征 = 只改本系统派生代码，不动大数据侧字段；大数据侧字段仅在真正新增原子事实时变动，两侧解耦。
本契约覆盖两个维度：product（短剧，日级）与 campaign（广告单元，小时级）。
## 2. 供给方式
维度与行粒度：
| 维度 | 行粒度 | 时间字段 | 消费接口 |
|---|---|---|---|
| product | 短剧视频 × 自然日 | `date` | `/api/lifecycle/product/detect` |
| campaign | campaign × 自然日 × 小时 | `date` + `hour` | `/api/lifecycle/campaign/detect` |
共同约定：
- 每自然日一个文件，按日整体供给/替换，不做增量补丁。
- `date` 与文件名一致，文件名主键即日期。
- 文件顶层带 meta：
  ```json
  { "meta": { "date": "YYYY-MM-DD", "version": "1.0", "generated_at": "<ISO 时间>" }, "rows": [...] }
  ```
campaign 小时级细则：
- `hour` 取 0~23，与 `date` 共同构成时间主键；全表同一时区，归因小时口径。
- 小时序列必须连续；缺失小时按断档处理（见 §6），不允许跳空补零。
## 3. 字段基线（全部原子事实）
### 3.1 product（日级）
| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `date` | date | 是 | 数据归属日 |
| `videoId` | string | 是 | 短剧视频 ID（主体键） |
| `language` | string | 是 | 语言代码，下游模板分流必需 |
| `scriptNo` | string | 是 | 剧本编号，信号携带给下游 |
| `videoName` | string | 否 | 展示名，可空 |
| `spend` | number ≥ 0 | 是 | 当日消耗（金额，单位见 §5） |
| `incomeOrder` | number ≥ 0 | 是 | 当日订单（充值）收入 |
| `incomeAd` | number ≥ 0 | 是 | 当日广告分成（IAA）收入 |
| `impressions` | number ≥ 0 | 是 | 当日展示量 |
| `clicks` | number ≥ 0 | 是 | 当日点击量 |
### 3.2 campaign（小时级）
| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `date` | date | 是 | 数据归属日 |
| `hour` | int 0~23 | 是 | 数据归属小时 |
| `campaignId` | string | 是 | 广告单元 ID（主体键） |
| `language` | string | 是 | 语言代码，下游模板分流必需 |
| `spend` | number ≥ 0 | 是 | 当小时消耗 |
| `incomeOrder` | number ≥ 0 | 是 | 当小时订单（充值）收入 |
| `incomeAd` | number ≥ 0 | 是 | 当小时广告分成（IAA）收入 |
| `impressions` | number ≥ 0 | 是 | 当小时展示量 |
| `clicks` | number ≥ 0 | 是 | 当小时点击量 |
## 4. 编码硬约束
- 数值一律为 number，**禁用字符串 / 百分比 / 千分位**（消灭现网 `"38.06%"` 类解析耦合）。
- 无值即显式 `0`，不允许 null / 缺键。
- 金额币种与单位全表统一（沿用现网口径，随 version 记录；变更须升版本并同步本系统）。
## 5. 口径定义（与大数据侧逐条对死）
- `spend`：消耗；`incomeOrder`：回款订单充值收入；`incomeAd`：广告分成（IAA）收入；三者同币种、同归因时间粒度（product 按日、campaign 按小时）。
- **ROI = (incomeOrder + incomeAd) / spend —— 由本系统计算，不在供给内。**
## 6. 覆盖率与断档约定（关键，决定判定有效性）
- 入表口径 = 当日有消耗（spend > 0）的全部主体，全量、非 TopN。
- 现网 `data/video_daily/*.json` 为每日 Top50 抽取（按消耗倒序取前 50）：亏损/关停主体一旦停投即从表中消失，本系统**无法区分「停投关停」与「漏数」**，`冷死亡 / 衰退 / 退出` 类生命周期判定将失真。契约须改为全量有消耗口径。
- 断档校验由本系统加载层执行：product 校验日期连续性；campaign 校验小时连续性（跨自然日按绝对小时序号判定）。
## 7. 本系统派生层职责（不在供给内）
从 §3 原子字段本地计算，供生命周期判定消费：
- product：日 ROI、跨日累计收入 / 消耗、观测跨度（首见日 ~ 末日）、近 N 日 ROI 序列与均值。
- campaign：0-24h / 24-72h / 72h+ 三段收入与消耗、观测小时跨度（首见小时 ~ 末小时）、分段 ROI 与峰值 ROI。
## 8. 明确不供清单（砍掉耦合）
以下为现网已出现、但属派生指标或口径混乱变体，**一律不供、本系统不再消费**：
`roi / newRoi / d0AdRoi`、`cpmPlatform / cpcPlatform`、`arppu`、`costSamePeriod`（环比）、`meetStandardRate / comprehensiveMeetStandardRate`、`subscriptionUserRate`、`costTotal / rechargeAmountTotal / d0IaaTotals / rechargeMediaTotal / rechargeNsNewTotal` 等全部 `*Total` 汇总变体，以及 `rechargeAmount / newUserRechargeAmount / rechargeAmt` 之间取数歧义（合并为 `incomeOrder`）。
## 9. 开放校验点（整合 PRD 前须有结论）
1. **40% 盈利线口径校验**：契约收入 = 订单 + 广告，分子比现网充值口径大，ROI 整体抬高；历史 40% 阈值是在充值口径下标定 → 上线/整合前须用含 `incomeAd` 的历史回算校验，或先双轨（ROI 暂只算 `incomeOrder` 对齐 40% 线，`incomeAd` 收数但暂不进分子）。
2. 现网 `d0Iaa` 可反推历史 `incomeAd`，用于上述回验。
## 10. 与现网字段的映射参考
| 契约字段 | 现网对应（netshort 看板） | 备注 |
|---|---|---|
| `spend` | `cost` | — |
| `incomeOrder` | `rechargeAmt` | 弃其余充值变体 |
| `incomeAd` | 由 `d0Iaa` 反推 / `d0AdRoi × cost` | 口径待对死 |
| `impressions` | `showCnt` | — |
| `clicks` | `clickCnt` | — |
| `language` | `language` | — |
| `scriptNo` | `videoRemark` | — |
| `videoName` | `videoName` | — |
