<div align="center">

<h1 align="center">SmartCS ResolutionOps Console</h1>

<p align="center">
  <a href="https://github.com/Nguxw/Smart_CS/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Nguxw/Smart_CS/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="FastAPI Agent API" src="https://img.shields.io/badge/FastAPI-Agent%20API-009688">
  <img alt="React 18" src="https://img.shields.io/badge/React-18-61DAFB">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green">
</p>

<p align="center"><strong>面向电商售后流程的 AI 客服运营控制台，强调治理、可观测性与可回归评测。</strong></p>

<p align="center">
SmartCS ResolutionOps Console 展示了如何把 LLM Agent 包装在显式工作流、
受控业务工具、服务案件状态、RAG 证据、人工确认、可观测性和回归评测体系之中。
</p>

<p align="center">
这个仓库按正式工程作品组织：默认可以无 API Key 本地运行，也可以通过 Docker Compose
切换到 PostgreSQL、Redis、Qdrant 等真实服务，并且 README 中的截图来自实际运行的本地应用。
</p>

<p align="center">
  <a href="../README.md">English README</a> ·
  <a href="architecture.md">架构说明</a> ·
  <a href="resume_notes.md">简历要点</a> ·
  <a href="../LICENSE">MIT License</a>
</p>

</div>

## 目录

- [产品定位](#产品定位)
- [截图](#截图)
- [系统架构](#系统架构)
- [核心能力](#核心能力)
- [技术栈](#技术栈)
- [仓库结构](#仓库结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [开发与验证](#开发与验证)
- [评测体系](#评测体系)
- [API 概览](#api-概览)
- [部署说明](#部署说明)
- [安全与治理](#安全与治理)
- [已知限制](#已知限制)
- [路线图](#路线图)
- [协议](#协议)

## 产品定位

SmartCS 模拟的是一个 AI 辅助售后坐席平台。Agent 可以识别客户意图，把每轮会话绑定到服务案件，检索相关政策证据，通过策略运行时调用业务工具，在副作用操作前暂停等待客户确认，并在需要时创建人工工单。

项目关注的不是简单聊天，而是 Agent 进入业务系统时需要的工程控制层：可追踪、可审计、可测试、可回放、可评估、可安全降级。

## 截图

### 坐席工作台

![SmartCS agent desk](assets/screenshots/desk.png)

### 人工工单队列

![SmartCS ticket queue](assets/screenshots/tickets.png)

### AgentOps 运行时视图

![SmartCS AgentOps runtime](assets/screenshots/system.png)

## 系统架构

```mermaid
flowchart LR
  Customer["客户 / 坐席"] --> Console["React ResolutionOps Console"]
  Console --> API["FastAPI SSE API"]
  API --> Orchestrator["Agent Orchestrator"]
  Orchestrator --> Plan["ActionPlan"]
  Orchestrator --> Retrieval["RAG Retrieval"]
  Orchestrator --> Policy["ToolRuntime + ToolPolicy"]
  Policy --> Tools["MCP-style Business Tools"]
  Tools --> Repository["PostgreSQL / In-memory Repository"]
  API --> Runtime["Redis / In-memory Runtime"]
  Retrieval --> Knowledge["Qdrant / In-memory Knowledge Store"]
  Orchestrator --> Harness["Regression Evaluation Harness"]
```

当前实际执行器是显式 orchestrator sequence，同时暴露 LangGraph-compatible workflow metadata，便于后续迁移到图执行器。

工作流顺序：

```text
router -> input_policy -> action_planner -> case_binding -> retrieve_policy
-> tool_policy -> human_confirm -> human_handoff -> guardrail
-> compose_answer -> memory_writer
```

## 核心能力

| 模块 | 已实现能力 |
| --- | --- |
| Agent 规划 | 意图识别、槽位抽取、最近订单解析、风险等级、缺失槽位、所需工具、确认和人工接管需求。 |
| 服务案件 | Case 台账、状态、当前任务、关联工单、关联订单、风险等级、处理摘要和审计证据。 |
| 工具治理 | MCP-style 工具注册、AuthContext 绑定、ToolPolicy、风险等级、确认边界、幂等键和审计日志。 |
| 人工确认 | 中高风险副作用工具可生成 pending task，经显式确认后恢复执行。 |
| 人工接管 | 不安全、隐私敏感或复杂售后场景可创建人工工单，保留建议回复和关联会话。 |
| RAG | 内置知识文档、本地确定性 embedding、可选语义 embedding、Qdrant、metadata filter、rerank hook 和 grounding 指标。 |
| 流式前端 | 通过 SSE 展示 agent steps、ActionPlan、case/task update、tool call、citation、token、final 和 error。 |
| 评测体系 | 覆盖 intent、tool、argument、missing slot、forbidden tool、RAG grounding、safety、handoff、task success 和 latency。 |
| 可观测性 | Conversation snapshot、trace ID、agent step、tool call、Redis stream state 和 runtime health。 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 API | Python 3.10+、FastAPI、Pydantic、Uvicorn |
| Agent Runtime | 显式 orchestrator、LangGraph-compatible metadata、Mock LLM、OpenAI-compatible client |
| 数据层 | PostgreSQL adapter、Redis adapter、Qdrant adapter、in-memory fallback |
| 前端 | React 18、TypeScript、Vite、lucide-react、自定义运营控制台 UI |
| 评测 | Pytest、确定性 mock provider、JSONL fixtures、RAG retrieval eval |
| 基础设施 | Docker Compose、PostgreSQL、Redis、Qdrant、Jaeger、Prometheus、Grafana |

## 仓库结构

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/        # Router、planner、orchestrator、guardrails
│   │   ├── api/           # FastAPI app 与 API routes
│   │   ├── data/          # In-memory 与 PostgreSQL repositories
│   │   ├── evals/         # Agent regression 与 RAG eval
│   │   ├── rag/           # Knowledge store、embedding、grounding、Qdrant
│   │   ├── runtime/       # Redis runtime state 与限流
│   │   └── tools/         # Business tools 与 policy runtime
│   ├── data/kb/           # 种子知识库 markdown
│   └── tests/             # 后端测试
├── frontend/
│   ├── src/
│   │   ├── app/           # 布局与导航
│   │   ├── hooks/         # API 状态 hooks
│   │   ├── pages/         # Desk、cases、tickets、knowledge、evals、AgentOps
│   │   └── services/      # API 与 SSE client
│   └── nginx.conf
├── docs/
│   ├── assets/screenshots # README 截图
│   ├── architecture.md
│   ├── demo-script.md
│   └── README.zh-CN.md
├── scripts/
├── docker-compose.yml
├── start_smartcs.ps1
└── README.md
```

## 快速开始

### 前置条件

- Windows PowerShell 5+ 或 PowerShell 7+
- Conda 或 Miniconda
- Docker Desktop，仅真实服务模式需要
- Git

默认演示使用确定性 mock LLM，不需要模型 API Key。

### 方式一：Windows 一键演示

```powershell
Copy-Item .env.example .env
.\start_smartcs.ps1 -Mock
```

脚本会创建或复用项目内 Conda 环境，安装依赖，启动 PostgreSQL、Redis、Qdrant、FastAPI 和 Vite，并写入演示数据。

常用参数：

```powershell
.\start_smartcs.ps1 -Mock -NoBrowser
.\start_smartcs.ps1 -Mock -NoDocker -SkipSeed
.\start_smartcs.ps1 -NoInstall
```

默认访问地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://127.0.0.1:5173` |
| 后端 API 文档 | `http://127.0.0.1:8000/docs` |
| Qdrant dashboard | `http://127.0.0.1:6333/dashboard` |
| Jaeger | `http://127.0.0.1:16686` |
| Prometheus | `http://127.0.0.1:9090` |
| Grafana | `http://127.0.0.1:3000` |

### 方式二：纯内存后端模式

```powershell
$env:LLM_PROVIDER="mock"
$env:DATA_BACKEND="memory"
$env:REDIS_BACKEND="memory"
$env:KB_BACKEND="memory"
.\.conda\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000
```

另开终端：

```powershell
cd frontend
$env:npm_config_cache="..\.npm_cache"
..\.conda\npm.cmd install
..\.conda\node.exe node_modules\vite\bin\vite.js --host 127.0.0.1
```

### 方式三：真实服务模式

```powershell
docker compose up -d postgres redis qdrant

$env:DATA_BACKEND="postgres"
$env:REDIS_BACKEND="redis"
$env:KB_BACKEND="qdrant"
$env:DATABASE_URL="postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs"
$env:REDIS_URL="redis://localhost:6379/0"
$env:QDRANT_URL="http://localhost:6333"

.\.conda\python.exe scripts\seed_demo_data.py
.\.conda\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000
```

## 配置说明

复制 `.env.example` 为 `.env`。`.env` 已被 Git 忽略。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | 可选 `mock`、`openai-compatible`、`ollama`。 |
| `LLM_MODEL` / `MODEL_NAME` | `gpt-4o-mini` | 模型名称。 |
| `OPENAI_API_KEY` | 空 | OpenAI-compatible provider 需要。 |
| `OPENAI_BASE_URL` / `OPENAI_API_BASE` | `https://api.openai.com/v1` | OpenAI-compatible endpoint。 |
| `DATA_BACKEND` | `.env.example` 中为 `postgres` | 可选 `memory`、`postgres`、`auto`。 |
| `REDIS_BACKEND` | `.env.example` 中为 `redis` | 可选 `memory`、`redis`、`auto`。 |
| `KB_BACKEND` | `.env.example` 中为 `qdrant` | 可选 `memory`、`qdrant`、`auto`。 |
| `DATABASE_URL` | 本地 PostgreSQL URL | PostgreSQL 连接。 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis runtime state。 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint。 |
| `EMBEDDING_PROVIDER` | `local` | 本地确定性 embedding 或 `sentence-transformers`。 |
| `RATE_LIMIT_PER_MINUTE` | `30` | 每用户限流。 |

接入真实 OpenAI-compatible 模型：

```dotenv
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
MOCK_MODE=false
```

## 开发与验证

后端：

```powershell
.\.conda\python.exe -m pytest backend
.\.conda\python.exe -m ruff check backend\app backend\tests
```

前端：

```powershell
cd frontend
..\.conda\node.exe node_modules\typescript\bin\tsc --noEmit
..\.conda\node.exe node_modules\vite\bin\vite.js build
```

统一检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1 -WithServices
```

## 评测体系

Agent Regression：

```powershell
.\.conda\python.exe -m pytest backend\tests\test_eval_harness.py
```

RAG Retrieval Eval：

```powershell
.\.conda\python.exe -m app.evals.rag_eval --backend memory
.\.conda\python.exe -m app.evals.rag_eval --backend qdrant
```

评测指标包括 intent accuracy、tool accuracy、tool argument accuracy、missing-slot accuracy、forbidden-tool violation、citation hit rate、groundedness、unsafe blocking、handoff precision、task success 和 latency。CI release gate 使用当前 22 条唯一 JSONL fixtures，不通过时阻断合并；详见 `docs/evaluation.md` 与 `docs/eval_report_mock.md`。

## API 概览

| Method | Path | 用途 |
| --- | --- | --- |
| `POST` | `/api/chat/stream` | SSE chat stream，包含 agent steps、ActionPlan、citations、tool calls、tokens 和 final state。 |
| `GET` | `/api/conversations/{conversation_id}` | 会话快照、messages、traces、cases、tasks 和 tool calls。 |
| `GET` | `/api/conversations/{conversation_id}/stream-state` | Runtime short memory 与 stream-event state。 |
| `GET` | `/api/cases` | 服务案件台账。 |
| `GET` | `/api/cases/{case_id}` | 案件详情、任务与工具审计。 |
| `POST` | `/api/tasks/{task_id}/confirm` | 确认 pending 副作用任务并恢复执行。 |
| `GET` | `/api/tickets` | 人工工单队列。 |
| `PATCH` | `/api/tickets/{ticket_id}` | 更新分配、回复、状态或结案字段。 |
| `POST` | `/api/kb/ingest` | 写入知识文档。 |
| `GET` | `/api/kb/search` | 知识库检索。 |
| `POST` | `/api/evals/run` | 运行确定性 Agent regression。 |
| `GET` | `/api/harness/manifest` | 工作流契约、发布门禁和工具元数据。 |
| `GET` | `/api/traces/{trace_id}` | 按 trace 查看 graph path、节点耗时、工具、引用和 guardrail 上下文。 |
| `GET` | `/health` | Runtime backend 和 provider 健康状态。 |
| `GET` | `/metrics` | Prometheus-style API、eval 和工具运行指标。 |

## 部署说明

仓库包含后端、前端 Dockerfile 以及本地依赖服务 Compose stack。

```powershell
docker compose up --build
```

Compose stack 包含：

- FastAPI backend
- Nginx-served frontend
- PostgreSQL
- Redis
- Qdrant
- Jaeger
- Prometheus
- Grafana

正式对外部署前应替换 demo credentials、配置持久化卷、收紧 CORS、使用 secret manager 管理 API Key，并接入真实认证授权。

## 安全与治理

- `.env` 文件不提交，`.env.example` 只包含安全占位值。
- `APP_ENV=local` 时允许 `X-SmartCS-User`、`X-SmartCS-Tenant`、`X-SmartCS-Roles`
  作为本地演示身份切换；非 local 环境需要 bearer token，并拒绝 demo header 提权。
- API 已按 RBAC 收口：customer 只能访问自己的资源，agent 可访问同 tenant 工单与 case，
  admin 才能访问 tools、harness、eval 和 graph runtime metadata。
- Case、Task、Ticket 状态流转通过显式状态机守护，避免直接把状态字段随意改成 resolved/closed。
- 工具调用绑定 `AuthContext` 并经过 `ToolPolicy`。
- 高风险副作用操作支持人工确认和幂等键。
- 隐私敏感或 prompt injection 场景可以拦截或升级为人工工单。
- 工具执行会写入审计元数据，可通过 case 和 conversation API 查看。

## 已知限制

- 当前认证层是 demo-oriented，生产环境需要替换。
- Mock LLM 适合确定性测试，但不能替代真实模型评估。
- 默认本地 embedding 追求可复现，不代表最佳语义效果。
- LangGraph 当前作为 workflow metadata 暴露，实际执行器是显式 orchestrator sequence。
- 种子数据为合成数据，主要服务于演示覆盖。

## 路线图

- 将现有 workflow contract 绑定到真实 LangGraph executor。
- 增加 agent、supervisor、admin 的 RBAC。
- 增加 eval-run 持久化和不同 prompt/model 版本趋势对比。
- 增加工单协同能力，例如内部备注和 SLA timer。
- 增加云端部署 manifests。

## 协议

本项目使用 [MIT License](../LICENSE)。
