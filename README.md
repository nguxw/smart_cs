# SmartCS ResolutionOps Console

SmartCS ResolutionOps Console is a resume-ready full-stack AI customer support project for e-commerce after-sales workflows. It demonstrates a Python/FastAPI agent runtime, service-case tracking, RAG knowledge search, governed business tool execution, conversation memory, guardrails, observability, and an evaluation harness, with a React operations console for live demos.

## Highlights

- Workflow contract: `router`, `input_policy`, `case_binding`, `retrieve_policy`, `tool_policy`, `human_confirm`, `human_handoff`, `guardrail`, `compose_answer`, `memory_writer`.
- Case operations: service cases, pending customer confirmations, task status, ticket linkage, and tool-audit evidence.
- Agent Harness: deterministic local evals for intent accuracy, tool selection, citation hit rate, PII leakage, and latency.
- Tool layer: MCP-style business tools for orders, refunds, invoices, tickets, and human handoff.
- Data layer: PostgreSQL persists orders, refunds, tickets, conversations, messages, agent steps, and tool traces.
- Redis: short-term conversation memory, SSE stream state, and per-user rate limiting.
- Qdrant: vector knowledge retrieval with deterministic local embeddings and metadata filters.
- Operations frontend: conversation handling, Case ledger, task/audit drill-down, ticket queue, knowledge management, and eval reports.
- Runnable without API keys: mock LLM and in-memory stores by default; OpenAI-compatible APIs, PostgreSQL, Redis, and Qdrant are configurable.

## Quick Start With Conda

### One-click Start on Windows

Copy `.env.example` to `.env` and fill your API key if you want real
OpenAI-compatible model calls. `.env` is ignored by git. Without `.env`, the app
starts in mock LLM mode.

```powershell
Copy-Item .env.example .env
.\start_smartcs.ps1
```

Or double-click:

```text
start_smartcs.bat
```

Useful options:

```powershell
.\start_smartcs.ps1 -NoBrowser      # do not open browser
.\start_smartcs.ps1 -SkipSeed       # skip idempotent demo data seed
.\start_smartcs.ps1 -Mock           # force mock LLM mode
.\start_smartcs.ps1 -NoInstall      # skip dependency checks
```

The script starts PostgreSQL, Redis, Qdrant, FastAPI, and Vite, then checks:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000/docs`
- Qdrant: `http://127.0.0.1:6333/dashboard`

```powershell
# Create a project-local Conda environment
$env:CONDA_PKGS_DIRS='F:\Project\Smart_CS\.conda_pkgs'
conda env create --prefix .\.conda --file environment.yml

# Optional: configure a real OpenAI-compatible gateway in an untracked .env
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_key
# OPENAI_API_BASE=https://your-compatible-endpoint/v1
# MODEL_NAME=your_model

# Backend
.\.conda\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000
```

In another terminal:

```powershell
cd frontend
$env:npm_config_cache='F:\Project\Smart_CS\.npm_cache'
..\.conda\npm.cmd install
..\.conda\node.exe node_modules\vite\bin\vite.js --host 127.0.0.1
```

Open `http://localhost:5173`.

## Run With Real Databases

```powershell
# Start PostgreSQL, Redis, and Qdrant
docker compose up -d postgres redis qdrant

# Option A: use the real data stores from local uvicorn
$env:DATA_BACKEND='postgres'
$env:REDIS_BACKEND='redis'
$env:KB_BACKEND='qdrant'
$env:DATABASE_URL='postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs'
$env:REDIS_URL='redis://localhost:6379/0'
$env:QDRANT_URL='http://localhost:6333'
.\.conda\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000

# Option B: Windows helper for the same local database setup
.\run_backend_db.bat
```

`run_backend_db.bat` only sets local database backends. If an untracked `.env` contains
`LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_API_BASE`, and `MODEL_NAME`, the same script
will use the real OpenAI-compatible model as well.

Seed richer synthetic demo data after the databases are running:

```powershell
.\run_seed_demo_data.bat
```

The seed is idempotent. It upserts synthetic users, orders, refunds, tickets, conversation
traces, and Qdrant knowledge-base documents without clearing existing runtime data.

`/health` reports the active backends:

```json
{
  "repository_backend": "postgresql",
  "runtime_backend": "redis",
  "knowledge_backend": "qdrant"
}
```

Local verification commands:

```powershell
.\.conda\python.exe -m pytest backend
.\.conda\python.exe -m ruff check backend\app backend\tests
cd frontend
..\.conda\node.exe node_modules\typescript\bin\tsc --noEmit
..\.conda\node.exe node_modules\vite\bin\vite.js build
```

## API Surface

- `POST /api/chat/stream`: SSE chat stream with `agent_step`, `tool_call`, `citation`, `token`, `final`, and `error` events.
- `GET /api/conversations/{conversation_id}`: conversation history and agent trace.
- `GET /api/conversations/{conversation_id}/stream-state`: Redis short memory and stream event state.
- `GET /api/tickets` and `PATCH /api/tickets/{ticket_id}`: ticket queue.
- `POST /api/kb/ingest` and `GET /api/kb/search`: knowledge ingestion and search.
- `POST /api/evals/run` and `GET /api/evals/{run_id}`: eval harness runs and reports.

## Resume Framing

Built a full-stack AI customer support operations console for e-commerce after-sales scenarios. The backend uses FastAPI and an explicit orchestrator sequence, with a LangGraph migration contract exposed as metadata, to coordinate routing, RAG retrieval, governed business tools, human confirmation, guardrail review, memory writing, and streaming answer composition. Added an evaluation harness that tracks intent accuracy, tool-call correctness, citation grounding, PII leakage, and latency across synthetic support cases.
