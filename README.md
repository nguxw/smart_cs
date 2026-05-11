# SmartCS ResolutionOps Console

[Chinese documentation](docs/README.zh-CN.md) | [Resume notes](docs/resume_notes.md) | [MIT License](LICENSE)

SmartCS is a local-first, full-stack AI customer support operations console for e-commerce after-sales workflows. It packages a FastAPI agent runtime, governed business tools, service-case tracking, RAG knowledge retrieval, human confirmation, observability, and deterministic evaluation into one resume-ready project.

The project runs without API keys in mock mode, but it can also connect to OpenAI-compatible LLM endpoints, PostgreSQL, Redis, and Qdrant for realistic demos.

## Screenshots

### Agent Desk

![SmartCS agent desk](docs/assets/screenshots/desk.png)

### Human Ticket Queue

![SmartCS ticket queue](docs/assets/screenshots/tickets.png)

### AgentOps Runtime

![SmartCS AgentOps runtime](docs/assets/screenshots/system.png)

## Why It Is Interesting

- Explicit agent workflow: `router -> input_policy -> action_planner -> case_binding -> retrieve_policy -> tool_policy -> human_confirm -> human_handoff -> guardrail -> compose_answer -> memory_writer`.
- ActionPlan before execution: every turn records intent, confidence, slots, required tools, missing slots, risk level, confirmation needs, and handoff requirements.
- Governed tool runtime: refund creation and handoff tools are wrapped with risk levels, confirmation boundaries, idempotency keys, authorization context, and audit logs.
- CaseOps data model: service cases, pending customer-confirmation tasks, linked tickets, conversations, agent steps, tool calls, and tool-audit evidence.
- RAG layer: seeded knowledge documents, local deterministic embeddings by default, optional sentence-transformers embeddings, Qdrant storage, metadata filters, reranking, and grounding scores.
- Agent evaluation harness: deterministic local regression cases for intent, tool selection, tool arguments, missing slots, forbidden tool calls, RAG grounding, PII leakage, handoff precision, task success, and latency.
- Operations console: React pages for live chat handling, case ledger, ticket queue, knowledge operations, release gates, and AgentOps runtime metadata.

## Architecture

```mermaid
flowchart LR
  U["Customer / Agent"] --> FE["React ResolutionOps Console"]
  FE --> API["FastAPI SSE API"]
  API --> WF["Agent Orchestrator"]
  WF --> PLAN["ActionPlan"]
  WF --> RAG["RAG Retrieval"]
  WF --> TOOLS["ToolRuntime + ToolPolicy"]
  TOOLS --> MCP["MCP-style Business Tools"]
  MCP --> PG["PostgreSQL / In-memory Repository"]
  API --> REDIS["Redis / In-memory Runtime"]
  RAG --> QDRANT["Qdrant / In-memory Knowledge Store"]
  WF --> EVAL["Evaluation Harness"]
```

## Tech Stack

- Backend: Python 3.10+, FastAPI, Pydantic, LangGraph-compatible workflow metadata, PostgreSQL adapter, Redis adapter, Qdrant adapter.
- Frontend: React 18, TypeScript, Vite, lucide-react, custom operations-console UI.
- Agent layer: deterministic mock LLM, OpenAI-compatible chat-completions client, business-tool registry, policy runtime, guardrails, eval harness.
- Infrastructure: Docker Compose for PostgreSQL, Redis, Qdrant, Jaeger, Prometheus, and Grafana.

## Quick Start

### Windows One-Command Demo

```powershell
Copy-Item .env.example .env
.\start_smartcs.ps1 -Mock
```

The script creates or reuses the project-local Conda environment, starts PostgreSQL, Redis, Qdrant, FastAPI, and Vite, seeds demo data, and prints the local URLs.

Useful options:

```powershell
.\start_smartcs.ps1 -Mock -NoBrowser
.\start_smartcs.ps1 -Mock -NoDocker -SkipSeed
.\start_smartcs.ps1 -NoInstall
```

Default local URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend API docs: `http://127.0.0.1:8000/docs`
- Qdrant dashboard: `http://127.0.0.1:6333/dashboard`

### Manual Local Run

```powershell
# Create the local environment once
$env:CONDA_PKGS_DIRS="$PWD\.conda_pkgs"
conda env create --prefix .\.conda --file environment.yml

# Backend
$env:LLM_PROVIDER="mock"
$env:DATA_BACKEND="memory"
$env:REDIS_BACKEND="memory"
$env:KB_BACKEND="memory"
.\.conda\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000
```

In another terminal:

```powershell
cd frontend
$env:npm_config_cache="..\.npm_cache"
..\.conda\npm.cmd install
..\.conda\node.exe node_modules\vite\bin\vite.js --host 127.0.0.1
```

Open `http://127.0.0.1:5173`.

## Real Services Mode

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

To use a real model, copy `.env.example` to `.env` and set:

```dotenv
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
MOCK_MODE=false
```

## Verification

```powershell
.\.conda\python.exe -m pytest backend
.\.conda\python.exe -m ruff check backend\app backend\tests
cd frontend
..\.conda\node.exe node_modules\typescript\bin\tsc --noEmit
..\.conda\node.exe node_modules\vite\bin\vite.js build
```

Unified checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1 -WithServices
```

RAG retrieval eval:

```powershell
.\.conda\python.exe -m app.evals.rag_eval --backend memory
.\.conda\python.exe -m app.evals.rag_eval --backend qdrant
```

## API Surface

- `POST /api/chat/stream`: SSE events for `agent_step`, `action_plan`, `tool_call`, `citation`, `token`, `final`, and `error`.
- `GET /api/conversations/{conversation_id}`: conversation history, agent steps, tool calls, linked cases, and tasks.
- `GET /api/conversations/{conversation_id}/stream-state`: Redis-backed short memory and stream state.
- `GET /api/cases` and `GET /api/cases/{case_id}`: service-case ledger and task/audit detail.
- `POST /api/tasks/{task_id}/confirm`: human confirmation for side-effect tools.
- `GET /api/tickets` and `PATCH /api/tickets/{ticket_id}`: human ticket queue.
- `POST /api/kb/ingest` and `GET /api/kb/search`: knowledge ingestion and retrieval.
- `POST /api/evals/run` and `GET /api/evals/{run_id}`: regression eval runs and reports.
- `GET /api/harness/manifest`: release gates, workflow contracts, tool metadata, and harness definition.

## Repository Hygiene

- Secrets belong in `.env`; `.env.example` is safe to commit.
- Local environments, dependency caches, build outputs, runtime data, logs, and IDE files are ignored by `.gitignore` and `.dockerignore`.
- README screenshots live in `docs/assets/screenshots/` and are generated from the running local app.
- Resume-facing talking points live in `docs/resume_notes.md` and `docs/resume.md`.

## License

This project is released under the [MIT License](LICENSE).
