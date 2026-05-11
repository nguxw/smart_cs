# SmartCS ResolutionOps Console

[English README](../README.md) | [简历要点](resume.md) | [MIT License](../LICENSE)

SmartCS 是一个面向电商售后场景的本地优先全栈 AI 客服运营控制台。项目把 FastAPI Agent 运行时、受控业务工具、服务案件跟踪、RAG 知识检索、人工确认、可观测性和确定性评测整合在一起，适合作为简历中的工程作品展示。

项目默认可以在 mock 模式下无 API Key 运行，也可以接入 OpenAI-compatible 模型、PostgreSQL、Redis 和 Qdrant 做更真实的演示。

## 截图

### 坐席工作台

![SmartCS agent desk](assets/screenshots/desk.png)

### 人工工单队列

![SmartCS ticket queue](assets/screenshots/tickets.png)

### AgentOps 运行时

![SmartCS AgentOps runtime](assets/screenshots/system.png)

## 项目亮点

- 显式 Agent 工作流：`router -> input_policy -> action_planner -> case_binding -> retrieve_policy -> tool_policy -> human_confirm -> human_handoff -> guardrail -> compose_answer -> memory_writer`。
- ActionPlan 先于工具执行生成：每轮会记录意图、置信度、槽位、所需工具、缺失槽位、风险等级、是否需要确认、是否需要人工接管。
- 受控工具运行时：退款、工单、人工接管等副作用工具通过风险等级、用户确认、幂等键、AuthContext 和审计日志保护。
- CaseOps 数据模型：服务案件、客户确认任务、关联工单、会话、Agent 步骤、工具调用和审计证据可追踪。
- RAG 能力：内置知识文档、默认本地确定性 embedding、可选 sentence-transformers、Qdrant 存储、元数据过滤、rerank 和 grounding score。
- Agent Regression 评测：覆盖 intent、tool selection、tool arguments、missing slots、forbidden tools、RAG grounding、PII 泄露、handoff precision、task success 和 latency。
- React 运营控制台：包含会话处理、服务案件台账、工单队列、知识运营、发布门禁和 AgentOps 元数据页面。

## 快速启动

### Windows 一键演示

```powershell
Copy-Item .env.example .env
.\start_smartcs.ps1 -Mock
```

脚本会创建或复用项目内 Conda 环境，启动 PostgreSQL、Redis、Qdrant、FastAPI 和 Vite，写入演示数据，并输出本地访问地址。

常用参数：

```powershell
.\start_smartcs.ps1 -Mock -NoBrowser
.\start_smartcs.ps1 -Mock -NoDocker -SkipSeed
.\start_smartcs.ps1 -NoInstall
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端 API 文档：`http://127.0.0.1:8000/docs`
- Qdrant Dashboard：`http://127.0.0.1:6333/dashboard`

## 真实服务模式

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

如需接入真实模型，复制 `.env.example` 为 `.env`，并设置：

```dotenv
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
MOCK_MODE=false
```

## 验证

```powershell
.\.conda\python.exe -m pytest backend
.\.conda\python.exe -m ruff check backend\app backend\tests
cd frontend
..\.conda\node.exe node_modules\typescript\bin\tsc --noEmit
..\.conda\node.exe node_modules\vite\bin\vite.js build
```

统一检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1 -WithServices
```

## 仓库整理

- `.env` 存放私密配置，`.env.example` 可以安全提交。
- 本地环境、依赖缓存、构建产物、运行数据、日志和 IDE 文件已通过 `.gitignore` / `.dockerignore` 忽略。
- README 截图位于 `docs/assets/screenshots/`，来自本地真实运行页面。
- 简历描述材料位于 `docs/resume_notes.md` 和 `docs/resume.md`。

## 协议

本项目使用 [MIT License](../LICENSE)。
