# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 后端 (Python 3.11+)
uv run uvicorn src.api.main:app --reload --port 8000    # 启动 API 服务
uv run pytest                                             # 运行全部测试
uv run pytest tests/unit/ -v                              # 仅运行单元测试
uv run pytest -k "test_name" -v                           # 运行指定测试

# 代码检查（修改文件后执行）
uvx ruff check --select E,F,W,I,S,PERF --ignore W291,W293,E203 --line-length 120 <file>
uvx mypy --strict <file>
uvx pyright <file>

# 前端
cd frontend && npm run dev      # 启动 Vite 开发服务器
cd frontend && npm run build    # 生产构建
cd frontend && npm run lint     # ESLint
```

## 架构

### 核心数据流：生命周期 → 策略 → 决策

```
指标数据 → LifecycleDetector (阶段判定) → StrategyEngine (策略匹配) → DecisionCommander (决策输出)
                ↑                              ↑                            ↑
         src/core/lifecycle/            src/core/strategy/         src/core/automation/
```

1. **生命周期引擎** (`src/core/lifecycle/`) — 基于 ROI 阈值将实体（商品/Campaign/素材）归入不同生命周期阶段。核心业务规则：**ROI > 40% 为盈利线**。关键时间节点：6h（快速通道信号）、24h（冷启动判定）、72h（关键决策点）、7d（持续盈利确认）。

2. **策略引擎** (`src/core/strategy/`) — 通过 `TriggerStageMapper` 将生命周期阶段匹配到预设策略。策略携带触发条件、冷却时间、时间窗口和规模配置。内置 `DEFAULT_STRATEGY_TEMPLATES`，覆盖冷死亡饱和攻击、成长期加预算、衰退期关停等场景。

3. **自动化指挥官** (`src/core/automation/`) — 将策略匹配结果转为 `Decision` 对象，写入 `logs/decisions/` 下的按日 JSONL 日志。

### auto_delivery 子系统 (`src/auto_delivery/`)

独立于核心策略引擎的自动化投放管线：
- `ApiClient` — 带认证的 HTTP 客户端，对接外部广告平台 API（凭证从 `config/credentials.json` 读取）
- `AutoDeliveryRunner` — 编排 3 步流程：查询达标素材 → 绑定素材到短剧 → 按语言分组创建投放任务
- `services/` — 各领域服务：素材、绑定、投放、渠道包、受众、报表

### API 层 (`src/api/`)

FastAPI 应用，4 个路由组：`/api/lifecycle`、`/api/automation`、`/api/strategy`、`/api/dashboard`。路由层很薄，直接委托给核心领域逻辑。

### 前端 (`frontend/`)

Vue 3 + Vite + TypeScript SPA，使用 Element Plus 组件库和 ECharts 图表。三个页面：Dashboard（看板）、Decisions（决策）、Strategy（策略）。状态管理用 Pinia，路由用 Vue Router。

### 配置

- `config/settings.py` — Pydantic Settings（读取 `.env`）；定义数据库 URL、Hive 配置、API 地址端口、轮询间隔
- `config/credentials.json` — 外部 API 认证凭证（已 gitignore）；模板见 `credentials.example.json`
- `pyproject.toml` — Hatchling 构建，pytest 启用 asyncio auto 模式，ruff 行宽 100

## 项目背景

智能基建系统——将"人工定期批量创建广告"升级为"系统实时自动耕作"。三个生命周期维度：商品（短剧）、素材、广告单元（Campaign）。各维度从观察期到衰退/关停期，阶段判定基于历史数据分析得出的 ROI 阈值。

## 开发原则

- 先讨论再写代码，每个功能先写测试，小步推进
- 领域防腐：核心模块依赖 Protocol/ABC，不直接依赖外部基础设施
- 扩展代修改：通过策略类/接口扩展，拒绝堆 if/else
- 公开接口全类型注解；捕捞具体异常；禁局部动态导入
- 不碰无关代码，不静默格式化文件
