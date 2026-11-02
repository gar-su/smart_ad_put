# MEMORY.md — 智能广告基建系统项目记忆

本文件记录项目持久的产品决策、功能改动与运行约定，供后续会话延续上下文。

## 项目定位（v4.0）

- 广告投放「决策指挥中心」：**只输出决策信号，不实际执行投放动作**。
- 决策端产出 `FOLLOW_UP` 跟投（建造）与 `ELIMINATE` 淘汰信号，交给下游 machine-delivery 新建或移除放量任务。
- 核心规则：**ROI > 40% 为盈利线**；收入 = d0_order_amt + d0_ad_amt。
- 关键时间节点：6h 快速通道、24h 冷启动判定、72h 生死判定、7d 持续盈利确认。

## 关键路径 / 命令

- 后端启动：`uv run uvicorn src.api.main:app --reload --port 8000`
- 前端 dev：`cd frontend && npm run dev`（Vite，端口 5173）
- 前端 build：`cd frontend && npm run build`（验证用，本次改动已通过）
- Python 测试：`uv run pytest`；本环境 venv 无 pytest/uv，用 `.venv/bin/python -c "..."` 做逻辑验证
- 配置源：`config/signal_rules.json`（单文件、纳入版本控制，pipeline 与 API 共用）

## 2026-09-07 产品改动记录

### 前端页面（`frontend/src/pages/`）
1. **全站「商品」文案统一为「短剧」**：
   - Dashboard 生命周期维度切换按钮「商品」→「短剧」
   - 概览卡片「总商品数」→「短剧总数」
   - Config 维度标签「商品（短剧）」→「短剧」
2. **诊断看板精简**：
   - 删除「盈利率」「自动化基建计划」两张卡片 → 现为 4 张：短剧总数、活跃广告、今日信号、跟投信号
   - 删除「ROI分布」「基建效率趋势（最近7天）」两图 → 图表区仅剩：今日信号类型分布、今日信号摘要
   - 明确 Dashboard **不接入真实后端**，静态兜底数据（用户要求）
3. **决策日志置信度语义**：表头加提示「置信度＝阶段判定可信度（0-100%），非盈利概率」
4. **信号配置页 Config 改为表格形式**：
   - 每阶段一行，维度/阶段/阶段标识/「跟投开关」/「冷却时长（小时）」
   - 开关文案由「值得跟投」改为「跟投开关」
   - 冷却时长按阶段输入，未开跟投开关时禁用输入

### 冷却机制：全局 → 按阶段（后端）
- `SignalRules`（`src/core/signal/config.py`）新增 `cooldown_map: dict[str, int]`（阶段→小时，按键须为合法 Stage、值须为正），保留 `cooldown_hours` 作为**全局默认兜底（24h）**
- `BuildSignalGenerator` 增加 `cooldown_map` 参数，`_cooldown_for(stage)` 按阶段查冷却，缺省回退全局默认；生成信号时用当前阶段冷却时长
- `run_pipeline.py` 构造生成器时传入 `cooldown_map=rules.cooldown_map`
- `config/signal_rules.json` 已加示例 `cooldown_map：{product_entry: 12, campaign_growth: 8}`
- 冷却键仍为 `(目标, 信号类型)`，同目标跨阶段共享冷却时间戳
- 测试补充：`tests/unit/test_signal_config.py`（cooldown_map 往返/非法键/非正值）、`test_signal_generator.py`（按阶段覆盖全局默认）

### 需求文档同步
- `PRD.md` 已同步：变更日志加 2026-09-07 一条、§5.5.2 触发控制/§5.3 生成流程/§5.8.1 流程图/§5.8.2 冷却检查改为按阶段、§5.6 看板卡片 6→4、图表区精简、商品→短剧、§5.5.3 confidence 补「阶段判定可信度，非盈利概率」

## 2026-09-09 诊断服务交付（给后端部署）

### 需求决策
- 交付物 = 接口契约 + 可跑镜像；服务边界**只做生命周期判定**——不取数、不生成信号、不存储
- 运行形态：常驻无状态 API；镜像含全部路由，交付契约只承诺 `/api/lifecycle/*`
- 入参：product 传日级原子事实、campaign 传小时级原子事实，**聚合在服务内做**；判定阈值保持硬编码（改阈值=重建镜像）
- 批量判定接口本期实现（兑现 PRD §6.1 的 1000+ 实体/次）
- 信号生成仍归主链路（`run_pipeline.py`），不在诊断服务内

### 代码
- 新增 `src/core/lifecycle/aggregation.py`：原子事实 → detector 入参（ROI / 分段收入成本 / 观测跨度），含空记录与时间断档校验
- `src/api/routers/lifecycle.py`：两个 detect 入参由聚合指标改为 `records`，新增 `POST /detect/batch`（≤1000）
- `src/api/main.py`：参数校验错误统一返回 400（原 FastAPI 默认 422）
- `tests/unit/test_aggregation.py` 11 例；全套 28 passed

### 交付件
- `Dockerfile` + `.dockerignore`（python:3.11-slim + uv，无持久化卷，健康检查 `/health`）
- 镜像实测：26 项 HTTP 断言全过（含断档 400、批量上限 400、campaign 缺 hour 400）
- `PRD.md` 新增 §5.8 诊断服务接口契约、§5.9 服务部署（容器交付：构建/启动/验证命令 + 部署约束表）；数据需求并入 §6.3（原 `docs/data_contract.md` 草案全文合并，草案文件已删）
- **PRD 定位收敛**：剥离技术架构描述（架构图、模块清单、文件路径、运行流程伪代码），PRD 只写产品需求；技术架构图移入 `docs/architecture.md`。仅生命周期诊断对外契约（§5.8）保留字段级约定

## 2026-11-02 素材选择策略（Phase 1：规则树 + 回测）

### 需求决策
- 与 `short-drama-scoring` 联动，但**不用 LightGBM 模型**；用本仓生命周期决策树的模式做素材选择
- 产物：素材级 `FOLLOW_UP` 信号（Phase 1 只回测，Phase 2 再落 API/信号链路）
- ROI 口径：合并口径 `(d0RechargeAmt + d0Iaa) / cost`；充值口径只做敏感性对照
- 活跃日 = `cost > 0` 的自然日；零消耗日不进入 ROI 序列、不做日历连续性硬校验

### 判定树
- `< 3` 活跃日 → `material_observing`
- `3-4` 活跃日：近3日ROI > 40% 且近2日消耗占比 ≥ 50% → `material_entry`；近3日ROI < 10% → `material_eliminated`
- `≥ 5` 活跃日：近3日ROI < 10% → 淘汰；达标后 ROI 较峰值降 > 50% 或 CTR 较前3日降 > 20% → `material_fatigue`；近3日ROI > 40% 且近2日ROI均值 ≥ 30% 且近2日消耗占比 ≥ 50% → `material_sustained`
- `material_entry` / `material_sustained` → `FOLLOW_UP(material)`；替换原 4 个无数据支撑的 CTR 经验阶段

### 回测结论（material_daily_v2.csv，14,423 素材 × 20 天）
- 留出集首次信号：lift **1.81x**，精确率 **38.4%**，覆盖 **31.9%**（基线 21.2%）
- Day3 入场：留出集 lift **1.78x**；Day5 稳定期：留出集 lift **2.58x** 但覆盖仅 3.7%
- 充值口径敏感性：留出集首次信号 lift **1.58x**（低于合并口径，说明 IAA 不计入会明显改变标签）
- 风险：幸存者偏差、单窗口数据、合并口径下 40% 线含义待 PRD §6.3 复核

### 代码
- `stages.py` 新增 5 个 `material_*` 阶段；`aggregation.py` 新增 `MaterialFact` / `MaterialMetrics` / `aggregate_material`；`detector.py` 重写 `MaterialLifecycleDetector` 并新增 `LifecycleDetector.detect_material`
- `tests/unit/test_material_lifecycle.py` 14 例；全套 42 passed
- `analysis_results/material_selection_backtest.py` + `analysis_results/material_selection/REPORT.md`
- **未做**：API 接口、信号链路、PRD 更新；跨仓缺口——打分仓 Kafka 消息体缺 `incomeAd` / `language`

## 2026-11-02 素材选品 A 方案（精确率优先）

### 需求决策
- 用户反馈 Phase 1 的 38.4% 精确率太低；重新评估后选择 A 档：在现有入场 / 稳定信号上加三道选品闸门
- 闸门：累计 ROI > 50%、ROI 波动率 <= 0.50、日均消耗 >= 200；三关全过才产 `FOLLOW_UP(material)`
- 保留生命周期阶段作为粗筛，不推翻现有判定树；阈值硬编码在 `MaterialThresholds`

### 回测结论
- 原始阶段首次信号：全集 1,252 条 / 37.1% / 1.76x；留出集 352 条 / 38.4% / 1.81x
- A 方案闸门后：全集 111 条（2.9%）/ 73.0% / 3.46x；留出集 37 条（3.4%）/ 73.0% / 3.44x
- 闸门逐级：1,252 → ROI 758 → 波动 215 → 消耗 111
- 时间稳定性：早期窗口 78.0%、后期窗口 70.0%
- 充值口径闸门后：全集 50 条 / 32.0%；留出集 16 条 / 37.5%

### 代码与文档
- `MaterialMetrics` 新增 `total_roi` / `avg_daily_cost` / `roi_cv`
- `MaterialLifecycleDetector.select` + `MaterialSelectionVerdict`；`detect_material` 快照带 `selected` / `selection_reason`
- `tests/unit/test_material_lifecycle.py` 20 例；全套 54 passed
- `analysis_results/material_selection/REPORT.md` 与 `report.html` 已更新为 A 方案口径
- 需求文档：`docs/material-selection-requirements.md`（按新规不回写 PRD）

### 边界
- 素材正式信号另行评审；打分仓零改动
- 日均消耗是系统已放量的反馈信号，选的是“已被证明”的素材，不是“被低估”的素材
- 标签是现有投放下的未来 ROI，不等于新任务的增量 ROI

## 2026-11-02 素材决策日志原型（前端展示）

- 背景：素材选品处于策略验证阶段；本次只改前端决策日志页做展示
- 决策日志页新增「目标维度」筛选（短剧 / 广告单元 / 素材），与信号类型可组合；切换筛选回到第 1 页
- 维度列新增「素材」标签
- 新增 4 条素材 mock `FOLLOW_UP` 信号，`reason` 带 A 方案闸门数值（累计 ROI / 波动率 / 日均消耗）
- 详情仍只展示标准字段 + 原始 JSON，不展示结构化闸门字段
- 需求文档：`docs/material-decisions-page-requirements.md`
- 验证：`npm run build` 通过；`pv` 20 条断言通过；`npm run lint` 因仓库缺 `eslint.config.js` 失败（改动前已如此）

## 2026-11-02 淘汰信号（ELIMINATE）

- 背景：短剧进入自动化投放任务后不会自动失效；新增 `ELIMINATE` 信号，下游停投并移除任务
- 触发：`product_exit` / `product_decline`（`eliminate_stages` 可配，默认这两个）
- 重入：允许，阶段回升到跟投区间后 `FOLLOW_UP` 自然重发；跟投与淘汰冷却独立
- 去重：本系统不做，下游按 `(target_dimension, target_id, signal_type)` 幂等
- 范围：本期只做短剧；Campaign 淘汰后续随数据源接入
- 代码：`SignalType` 加 `ELIMINATE`；`SignalRules.eliminate_stages` + 交集校验；`StageSignalMapper` 双列表注入；`run_pipeline.py` 传参；全套 54 passed
- 前端原型：决策日志加淘汰筛选/红色 tag/示例信号；看板类型分布与摘要加淘汰；配置页由「跟投开关」改为每阶段「信号类型」下拉（跟投 / 淘汰 / 不产出）
- 需求文档：`docs/eliminate-signal-requirements.md`（PRD.md 不回写；自本次起新增需求写入独立文档）

## 2026-11-02 决策信号需求合并 + 全站信号类型

- 新增主文档 `docs/decision-signals-requirements.md`，合并 `eliminate-signal-requirements.md` 与 `material-decisions-page-requirements.md`；两份旧文档文件头标注“已被取代”，保留作历史
- 主文档覆盖：`FOLLOW_UP` / `ELIMINATE` 信号总览、淘汰信号完整口径、素材维度展示、Dashboard / Decisions / Config 三页原型改动、验收标准
- Dashboard 概览卡片 5→6，新增「淘汰信号」红色卡片与「活跃素材」卡（位于活跃广告右侧）；生命周期分布新增「素材」维度（5 个阶段）；信号类型分布与摘要已含跟投 + 淘汰
- Config 保持每阶段跟投 / 淘汰 / 不产出；阶段列表新增素材 5 个阶段，`material_entry` / `material_sustained` 默认跟投，其余不产出
- 验证：`npm run build` 通过；`pv` 22 条断言通过；`npm run lint` 仍受仓库缺 `eslint.config.js` 影响

## 2026-11-02 素材 FOLLOW_UP 产品口径（Day 2 首判）

- 产品口径：第 2 个活跃日首判；第 1 天观察；2-4 天入场，>= 5 天稳定；A 方案三道闸门；冷却 24h
- 数据需求：素材 × 自然日，全量有消耗；字段 material_id / date / language_code / script_no / shortplay_name / spend / income_order / income_ad / impressions / clicks；最少 2 个活跃日，建议保留 14 天
- 回测：留出集 day2 51 条 / 2.9% / 78.4%；day3 39 条 / 3.5% / 74.4%；day1 57.1% / 1.1% 不采用；day2 早期 / 后期 86.7% / 75.0%
- 产出逻辑与数据需求已写入 `docs/decision-signals-requirements.md` §4
- 当前检测器仍按第 3 天，待按新产品口径调整

## 待办 / 注意事项

- **git 已提交并推送至 GitHub**（`dbffabc` 结构清理+诊断服务、`22787bd` gitignore、`feee551` 数据需求并入 PRD）；`config/credentials.json` 已删；未跟踪的 `data_pages/`、`fetch_*.py`、`shortplay_daily_data.json`（~42MB，4 月抓取数据，用户要求保留）已进 `.gitignore`，不入库
- 测试：`uv run pytest` 可跑（54 passed）；docker / uvicorn / curl 在本环境均可正常执行

## 常用技术栈

Python 3.11+ / FastAPI / Pydantic v2 / Vue 3 + Vite + TS + Element Plus + ECharts。后端代码在 `src/`，交付件 `Dockerfile`（python:3.11-slim + uv）。