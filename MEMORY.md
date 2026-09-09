# MEMORY.md — 智能广告基建系统项目记忆

本文件记录项目持久的产品决策、功能改动与运行约定，供后续会话延续上下文。

## 项目定位（v4.0）

- 广告投放「决策指挥中心」：**只输出决策信号，不实际执行投放动作**。
- 决策端本期唯一产出 `FOLLOW_UP` 跟投（建造）信号，交给下游 machine-delivery 新建放量任务。
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
- `PRD.md` 新增 §5.8 诊断服务接口契约；数据需求并入 §6.3（原 `docs/data_contract.md` 草案全文合并，草案文件已删）
- **PRD 定位收敛**：剥离技术架构描述（架构图、模块清单、文件路径、运行流程伪代码），PRD 只写产品需求；技术架构图移入 `docs/architecture.md`。仅生命周期诊断对外契约（§5.8）保留字段级约定

## 待办 / 注意事项

- **git 改动未提交**：本轮结构清理 + 诊断服务改造（含 PRD/CLAUDE.md/文档）均未提交；`config/credentials.json` 已删，未跟踪的 `data_pages/`、`fetch_*.py`、`shortplay_daily_data.json`（~42MB，4 月抓取数据，用户要求保留）不在提交范围
- **本环境提交/端口限制**：沙箱内 git 写 `.git` 与 Vite 监听端口被拒；宿主提权又被 active filesystem profile 的 denied reads 拦截（`elevation_forbidden_denied_reads`）。落地方式：用户在宿主终端自行 `git add`/`git commit`、自行起 uvicorn + vite
- 测试依赖：项目用 uv 管理，本机 venv 无 pytest；需要完整跑测试应在有 uv/pytest 的环境执行

## 常用技术栈

Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy / Vue 3 + Vite + TS + Element Plus + ECharts。顶层 `smart_ad_put/` 为空，实际后端代码在 `src/`。