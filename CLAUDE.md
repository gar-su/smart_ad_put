# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库定位

产品经理 + 数据分析师的工作仓库：**需求文档 + 决策诊断服务**。仓库里没有执行侧代码——系统只输出决策信号，不实际执行投放动作。

- `PRD.md` 是既有产品行为的基线文档，**只写产品需求、不写技术架构**；**后续新增需求一律写入 `docs/` 下的独立需求文档**（主文档：`docs/decision-signals-requirements.md`；另有 `docs/material-selection-requirements.md`；历史：`docs/eliminate-signal-requirements.md`、`docs/material-decisions-page-requirements.md`），不再回写 PRD.md；技术架构图见 `docs/architecture.md`，判定服务对外契约见 PRD §5.8、容器交付见 §5.9；`MEMORY.md` 记产品改动沿革
- 数据供给需求见 `PRD.md` §6.3（短剧日级 + 广告单元小时级字段基线）；文末「待定决策」2 条是上线前须有结论的业务项
- `docs/data_contract.md` **已删除**（草案全文并入 PRD §6.3）；`src/core/lifecycle/aggregation.py`、`src/api/routers/lifecycle.py`、`tests/unit/test_aggregation.py` 的注释仍指向该文件——注释里的引用不代表文件存在
- `analysis_results/*/REPORT.md` + `docs/lifecycle-threshold-validation.md` 是 ROI 阈值的数据依据（改阈值前先看这里）。报告可读，但多数 `analysis_results/*.py` 从仓库外的绝对路径（`/Users/gar/PyCharmMiscProject/data_chunks_*`）读 parquet，**在本仓库跑不通**，别试图复现；例外是 `analysis_results/material_selection_backtest.py`，它读 `short-drama-scoring/data/material_daily_v2.csv`，可跑
- `frontend/` 是 PRD §5.1 的「在线原型」，由 `.github/workflows/deploy.yml` 构建部署到 GitHub Pages

## 常用命令

```bash
# 后端（Python 3.11+，uv 管理）
uv run uvicorn src.api.main:app --reload --port 8000   # 启动 API 服务
uv run python run_pipeline.py                          # 主循环：读日数据 → 产出 FOLLOW_UP / ELIMINATE 信号

uv run pytest                                          # 全部测试（当前仅 tests/unit/）
uv run pytest tests/unit/test_signal_generator.py -v   # 单文件
uv run pytest tests/unit/test_signal_generator.py::test_cooldown_suppresses_repeat -v  # 单测试

# 代码检查（修改文件后执行）
uvx ruff check --select E,F,W,I,S,PERF --ignore W291,W293,E203 --line-length 120 <file>
uvx mypy --strict <file>

# 前端
cd frontend && npm install && npm run dev   # Vite dev（端口 3000，/api 代理到 8000）
cd frontend && npm run build                # 生产构建
cd frontend && npm run lint                 # ESLint
```

## 项目定位（v4.0）

**决策指挥中心：只输出决策信号，不实际执行投放动作。** 本期产出 `FOLLOW_UP` 跟投（建造）与 `ELIMINATE` 淘汰信号，交给下游 machine-delivery 新建或移除放量任务。放量规模由下游模板承载，本系统只给意图（信号不带 scale）。

核心业务规则：**ROI > 40% 为盈利线**；收入 = d0_order_amt + d0_ad_amt。关键时间节点：6h（快速通道）、24h（冷启动判定）、72h（关键决策点）、7d（持续盈利确认）。

## 架构

全部代码在 `src/`（hatchling 打包 src）。

### 核心数据流：日数据 → 生命周期 → 建造信号

```
data/video_daily/*.json ──(run_pipeline.py 逐视频跨日聚合)→
ProductLifecycleDetector (ROI/成本/观测时长 → 生命周期阶段)
StageSignalMapper (阶段 → 信号类型，follow_up_stages / eliminate_stages 限定)
BuildSignalGenerator (组装 BuildSignal + 按阶段冷却)
logs/decisions/YYYY-MM-DD/decisions.jsonl
```

1. **生命周期引擎** (`src/core/lifecycle/`) — `stages.py` 定义 `Dimension`（product/campaign/material）、`Stage`（19 个阶段，product_* / campaign_* / material_* 前缀）、`LifecycleRecord`；`detector.py` 内含三个检测器 + `LifecycleDetector` 门面，将 ROI/成本/观测时长归入阶段，输出阶段、置信度与判因。`material_*` 产品口径为第 2 个活跃日首判 + A 方案选品闸门（累计 ROI>50% / 波动率≤0.5 / 日均消耗≥200，留出集 78.4%）；当前检测器仍按第 3 天，待按新产品口径调整。

2. **建造信号引擎** (`src/core/signal/`) — 取代旧策略引擎（原 `src/core/strategy/` 已删）：
   - `mapper.py` `StageSignalMapper`：阶段 → `SignalType`，可跟投阶段列表由规则注入
   - `generator.py` `BuildSignalGenerator`：组装 `BuildSignal` + 冷却控制（冷却键 = (目标, 信号类型)；`cooldown_map` 按阶段覆盖全局 `cooldown_hours` 默认）
   - `models.py`：对外契约 `BuildSignal`（`signal_id` 幂等键、`language_code`/`script_no` 供下游分流），`SignalType` 本期实现 `FOLLOW_UP` / `ELIMINATE`，其余挂起
   - `config.py` `SignalRules`：读写 `config/signal_rules.json`

3. **主循环** (`run_pipeline.py`) — 数据源 `data/video_daily/*.json`（按日 top50 短剧视频指标），聚合 → 判定 → 映射＋冷却 → 追加信号到 `logs/decisions/` 按日 JSONL（与旧决策日志同目录/格式）。数据源里的 `roi` 是百分比字符串（`"43.72%"`），由 `parse_roi` 解析，解析失败记 0。

### 两条独立入口，收入口径不同

pipeline 与 API 是两个互不调用的入口，喂给同一个检测器的收入定义并不一致：

- **pipeline**：读现网字段 `rechargeAmt`（下单口径）+ `cost`（都是**字符串**，得 `float()` 转换），判定输入的 `recent_roi_history` 直接取平台给的 `roi` 百分比串；数据里**没有** `incomeAd`。
- **API**：读契约字段 `records[].incomeOrder / incomeAd / spend`，ROI 一律由服务内的 `aggregation.py` 现算。

PRD §6.3「待定决策 1」（40% 线是否双轨）说的就是这处口径差——改阈值或对账前先分清在说哪条链路。

### 必须知道的坑

- **冷却只在单次进程内有效**：`BuildSignalGenerator._last_sent` 是内存字典，`run_pipeline.py` 每次运行都新建生成器，所以重复运行会把同一批信号再追加一遍（`logs/decisions/2026-09-01/decisions.jsonl` 126 行 = 42 个目标各出现 3 次，分属 04:39:50 / 04:39:58 / 04:42:53 三批——实证）。跨进程持久化未实现，`generator.py` 注释里写明「本期不锁实现」。
- **数据源是 Top50 抽样**：`data/video_daily/*.json` 每日按消耗倒序取前 50，停投/关停的视频会从表中消失，系统无法区分「停投关停」与「漏数」，`cold_dead` / `decline` / `exit` 类判定会失真。契约要求改为「当日有消耗的全量」口径（PRD §6.3）。仓库里现有 8 天数据（2026-04-23 ~ 04-30），只够验证主链路。
- **`logs/` 被 `.gitignore` 忽略**：决策日志不入库，克隆后目录为空，`/api/signals*` 与 `/api/dashboard/summary` 会返回 0 条——属正常现象，不是接口坏了。

### API 层 (`src/api/`)

FastAPI 应用，3 个路由组（`main.py` 注册）：
- `/api/lifecycle` — `POST /product/detect`、`POST /campaign/detect`、`POST /detect/batch`（≤1000 实体）、`GET /stages`、`GET /thresholds`。**入参是原始原子事实 `records`，聚合在服务内做**（`src/core/lifecycle/aggregation.py`），对外契约见 PRD §5.8（注意 `routers/lifecycle.py` 顶部 docstring 写的是 §5.9，那是容器交付章节，指错了）
- `/api/signals` — `GET ""`、`GET /stats`、`GET /config`、`PUT /config`（读写 `signal_rules.json`）
- `/api/dashboard` — 读决策日志的看板汇总接口

路由层很薄，直接委托给核心领域逻辑或读 JSONL。参数校验错误统一返回 400（`main.py` 里的 `RequestValidationError` 处理器）。

### 前端 (`frontend/`)

Vue 3 + Vite + TypeScript SPA，Element Plus + ECharts，Pinia + Vue Router，dev 端口 3000（`/api` 代理到 8000）。**三个页面目前全是静态 mock**：`frontend/src` 里没有任何 `fetch`/`axios` 调用，Dashboard（看板）、Decisions（决策日志）、Config（信号配置）都不接后端，界面上挂「前端示例数据」标签；Dashboard 概览 6 张卡片含淘汰信号与活跃素材，生命周期分布支持素材维度；Decisions 页支持信号类型 + 目标维度双筛选，含 4 条素材示例信号；Config 页每阶段可选跟投 / 淘汰 / 不产出，阶段列表含素材 5 个阶段，编辑只改本地状态，不落盘。真正生效的信号配置是 `config/signal_rules.json`（`PUT /api/signals/config` 或直接改文件），改完需重跑 pipeline。

### 配置

- `config/settings.py` — Pydantic Settings（读取 `.env`）；`BASE_DIR`、`DECISION_LOG_DIR`、API 地址端口
- `config/signal_rules.json` — **单配置源**（`follow_up_stages` / `eliminate_stages` / `cooldown_hours` / `cooldown_map`），纳入版本控制，pipeline 与 `/api/signals/config` 共用读写；`SignalRules.load` 缺文件时用内置默认
- `pyproject.toml` — Hatchling 构建，pytest asyncio auto 模式，ruff 行宽 100（检查命令用 120）
- `Dockerfile` — 诊断服务镜像（python:3.11-slim + uv，`uvicorn src.api.main:app`，无持久化卷）

## 诊断服务交付（给后端部署）

服务边界只到判定：输入实体历史原子事实，输出生命周期阶段。不取数、不生成信号、不落盘。接口契约见 PRD §5.8，数据供给需求见 PRD §6.3（短剧日级 + 广告单元小时级）。

实际交付物是仓库根的 `smart-ad-put-diagnosis.tar`（`docker save` 导出，~89MB，已进 `.gitignore` 不入库），后端 `docker load -i` 导入即可；下面的 `docker build` 是源码自建路径。

```bash
docker build -t smart-ad-put-diagnosis:dev .
docker run -d --name smart-ad-put-diagnosis -p 8000:8000 smart-ad-put-diagnosis:dev
curl -s localhost:8000/health
```

镜像内只 `COPY src ./src` + `COPY config ./config`，**不含 `run_pipeline.py`、`data/`、`frontend/`**——容器里只有判定服务，信号生成链路不在交付范围内（改 `run_pipeline.py` 不会影响交付件，改 `detector.py`/`aggregation.py`/API 才会，且须重建镜像）。

## 测试现状

`tests/unit/` 共 54 个用例，覆盖三层：信号层（mapper / generator / config / ELIMINATE）、聚合层（`test_aggregation.py`：campaign 分段桶、跨午夜连续性、断档报错）与素材层（`test_material_lifecycle.py`：活跃日过滤、近 N 日指标、五阶段边界、三道选品闸门）。product / campaign 检测器（`detector.py`）与 API 路由**无测试覆盖**——改阈值或判定分支时需自行构造用例验证（`GET /api/lifecycle/thresholds` 只读暴露当前阈值，可用来核对）。

`uv run pytest` 会报 `Unknown config option: asyncio-mode`：`pyproject.toml` 里的键名应是 `asyncio_mode`（pytest-asyncio 只认下划线），当前没有 async 测试所以只警告不失败——写第一个 async 测试前先修这个键。

## 项目背景

智能基建系统——将"人工定期批量创建广告"升级为"系统实时自动耕作"。三个生命周期维度：商品（短剧）、素材、广告单元（Campaign）。各维度从观察期到衰退/关停期，阶段判定基于历史数据分析得出的 ROI 阈值。

## 开发原则

- 先讨论再写代码，每个功能先写测试，小步推进
- 领域防腐：核心模块依赖 Protocol/ABC，不直接依赖外部基础设施
- 扩展代修改：通过策略类/接口扩展，拒绝堆 if/else
- 公开接口全类型注解；捕捞具体异常；禁局部动态导入
- 不碰无关代码，不静默格式化文件
