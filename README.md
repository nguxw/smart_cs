# SmartCS ResolutionOps Console

[![CI](https://github.com/Nguxw/Smart_CS/actions/workflows/ci.yml/badge.svg)](https://github.com/Nguxw/Smart_CS/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-Agent%20API-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![License](https://img.shields.io/badge/License-MIT-green)

SmartCS ResolutionOps Console is a full-stack AI customer support operations platform for
e-commerce after-sales workflows. It demonstrates how an LLM agent can be wrapped with
explicit workflow contracts, governed business tools, service-case state, RAG evidence,
human confirmation, observability, and regression evaluation.

The repository is designed to be reviewed as a production-style portfolio project: it runs
locally without API keys, can switch to real infrastructure through Docker Compose, and
includes end-to-end UI screenshots generated from the running application.

[中文说明](docs/README.zh-CN.md) | [Architecture Notes](docs/architecture.md) | [Resume Notes](docs/resume_notes.md) | [MIT License](LICENSE)

## Table of Contents

- [Product Scope](#product-scope)
- [Screenshots](#screenshots)
- [System Architecture](#system-architecture)
- [Core Capabilities](#core-capabilities)
- [Technology Stack](#technology-stack)
- [Repository Layout](#repository-layout)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Development Workflow](#development-workflow)
- [Evaluation Harness](#evaluation-harness)
- [API Surface](#api-surface)
- [Deployment Notes](#deployment-notes)
- [Security and Governance](#security-and-governance)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

## Product Scope

SmartCS models an AI-assisted support desk for post-purchase commerce operations. The
agent can identify the customer intent, bind each turn to a service case, retrieve relevant
policy evidence, call business tools through a policy runtime, pause for customer
confirmation before side effects, create human tickets when escalation is needed, and
stream an auditable response back to the console.

The project focuses on the operational layer around an agent rather than a simple chat
demo. The main engineering question is: how do we make agent behavior traceable,
reviewable, testable, and safe enough for customer-service workflows?

## Screenshots

### Agent Desk

![SmartCS agent desk](docs/assets/screenshots/desk.png)

### Human Ticket Queue

![SmartCS ticket queue](docs/assets/screenshots/tickets.png)

### AgentOps Runtime View

![SmartCS AgentOps runtime](docs/assets/screenshots/system.png)

## System Architecture

```mermaid
flowchart LR
  Customer["Customer / Support Agent"] --> Console["React ResolutionOps Console"]
  Console --> API["FastAPI SSE API"]
  API --> Orchestrator["Agent Orchestrator"]
  Orchestrator --> Plan["ActionPlan"]
  Orchestrator --> Retrieval["RAG Retrieval"]
  Orchestrator --> Policy["ToolRuntime + ToolPolicy"]
  Policy --> Tools["MCP-style Business Tools"]
  Tools --> Repository["PostgreSQL or In-memory Repository"]
  API --> Runtime["Redis or In-memory Runtime"]
  Retrieval --> Knowledge["Qdrant or In-memory Knowledge Store"]
  Orchestrator --> Harness["Regression Evaluation Harness"]
```

The live executor is an explicit orchestrator sequence. A LangGraph-compatible workflow
contract is exposed as metadata so the runtime can migrate to a graph executor without
changing the API, tool, or evaluation contracts.

Workflow sequence:

```text
router -> input_policy -> action_planner -> case_binding -> retrieve_policy
-> tool_policy -> human_confirm -> human_handoff -> guardrail
-> compose_answer -> memory_writer
```

## Core Capabilities

| Area | What is implemented |
| --- | --- |
| Agent planning | Intent classification, slot extraction, latest-order resolution, risk level, missing slots, required tools, confirmation and handoff requirements. |
| Case operations | Service-case ledger, case status, current task, linked ticket, related order, risk level, resolution summary, and audit trail. |
| Tool governance | MCP-style business tools with AuthContext binding, ToolPolicy, risk levels, confirmation boundaries, idempotency keys, and audit logs. |
| Human confirmation | Medium/high-risk side-effect tools can create pending tasks and resume only after explicit approval. |
| Human handoff | Unsafe, privacy-sensitive, or operationally complex cases can create support tickets with suggested replies and linked conversations. |
| RAG | Seeded knowledge documents, deterministic local embeddings, optional semantic embeddings, Qdrant integration, metadata filters, reranking hooks, and grounding metrics. |
| Streaming UI | Server-sent events for agent steps, ActionPlan, case/task updates, tool calls, citations, tokens, final state, and errors. |
| Evaluation | Deterministic regression datasets for intent, tools, arguments, missing slots, forbidden tools, RAG grounding, safety, handoff, task success, and latency. |
| Observability | Conversation snapshots, trace IDs, agent step history, tool-call history, Redis stream state, and runtime health metadata. |

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Backend API | Python 3.10+, FastAPI, Pydantic, Uvicorn |
| Agent runtime | Explicit orchestrator, LangGraph-compatible metadata, mock LLM, OpenAI-compatible chat-completions client |
| Data stores | PostgreSQL adapter, Redis adapter, Qdrant adapter, in-memory fallback stores |
| Frontend | React 18, TypeScript, Vite, lucide-react, custom operations-console UI |
| Evaluation | Pytest, deterministic mock provider, JSONL case fixtures, RAG retrieval eval |
| Infrastructure | Docker Compose, PostgreSQL, Redis, Qdrant, Jaeger, Prometheus, Grafana |

## Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/        # Router, planner, orchestrator, guardrails
│   │   ├── api/           # FastAPI app and public API routes
│   │   ├── data/          # In-memory and PostgreSQL repositories
│   │   ├── evals/         # Regression and RAG evaluation harnesses
│   │   ├── rag/           # Knowledge store, embeddings, grounding, Qdrant
│   │   ├── runtime/       # Redis runtime state and rate limiting
│   │   └── tools/         # Business tools and policy runtime
│   ├── data/kb/           # Seed knowledge-base markdown files
│   └── tests/             # Backend regression tests
├── frontend/
│   ├── src/
│   │   ├── app/           # Layout and navigation
│   │   ├── hooks/         # API-backed state hooks
│   │   ├── pages/         # Desk, cases, tickets, knowledge, evals, AgentOps
│   │   └── services/      # API and SSE clients
│   └── nginx.conf         # Container runtime config
├── docs/
│   ├── assets/screenshots # README screenshots generated from the running UI
│   ├── architecture.md
│   ├── demo-script.md
│   └── README.zh-CN.md
├── scripts/               # Local health checks and demo data seeding
├── docker-compose.yml
├── start_smartcs.ps1
└── README.md
```

## Getting Started

### Prerequisites

- Windows PowerShell 5+ or PowerShell 7+
- Conda or Miniconda
- Docker Desktop, only required for PostgreSQL/Redis/Qdrant mode
- Git

The default demo can run with a deterministic mock LLM. No model API key is required.

### Option 1: One-command Windows demo

```powershell
Copy-Item .env.example .env
.\start_smartcs.ps1 -Mock
```

The script creates or reuses the project-local Conda environment, installs dependencies,
starts PostgreSQL, Redis, Qdrant, the FastAPI backend, and the Vite frontend, then seeds
demo data.

Useful flags:

```powershell
.\start_smartcs.ps1 -Mock -NoBrowser
.\start_smartcs.ps1 -Mock -NoDocker -SkipSeed
.\start_smartcs.ps1 -NoInstall
```

Default local URLs:

| Service | URL |
| --- | --- |
| Frontend | `http://127.0.0.1:5173` |
| Backend API docs | `http://127.0.0.1:8000/docs` |
| Qdrant dashboard | `http://127.0.0.1:6333/dashboard` |
| Jaeger | `http://127.0.0.1:16686` |
| Prometheus | `http://127.0.0.1:9090` |
| Grafana | `http://127.0.0.1:3000` |

### Option 2: In-memory backend mode

Use this mode when you want the fastest local smoke test without Docker services.

```powershell
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

### Option 3: Real services mode

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

## Configuration

Copy `.env.example` to `.env` for machine-local configuration. `.env` is ignored by Git.

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | `mock`, `openai-compatible`, or `ollama`. |
| `LLM_MODEL` / `MODEL_NAME` | `gpt-4o-mini` | Model name passed to the provider. |
| `OPENAI_API_KEY` | empty | Required for OpenAI-compatible providers. |
| `OPENAI_BASE_URL` / `OPENAI_API_BASE` | `https://api.openai.com/v1` | OpenAI-compatible chat-completions endpoint. |
| `DATA_BACKEND` | `postgres` in `.env.example` | `memory`, `postgres`, or `auto`. |
| `REDIS_BACKEND` | `redis` in `.env.example` | `memory`, `redis`, or `auto`. |
| `KB_BACKEND` | `qdrant` in `.env.example` | `memory`, `qdrant`, or `auto`. |
| `DATABASE_URL` | local PostgreSQL URL | SQLAlchemy-style PostgreSQL URL using psycopg. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis runtime state URL. |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint. |
| `EMBEDDING_PROVIDER` | `local` | Deterministic local embeddings or `sentence-transformers`. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per-user API rate limit. |

To use a real OpenAI-compatible model:

```dotenv
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
MOCK_MODE=false
```

## Development Workflow

Backend checks:

```powershell
.\.conda\python.exe -m pytest backend
.\.conda\python.exe -m ruff check backend\app backend\tests
```

Frontend checks:

```powershell
cd frontend
..\.conda\node.exe node_modules\typescript\bin\tsc --noEmit
..\.conda\node.exe node_modules\vite\bin\vite.js build
```

Unified local checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check_local.ps1 -WithServices
```

## Evaluation Harness

The backend includes two complementary evaluation paths.

Agent regression:

```powershell
.\.conda\python.exe -m pytest backend\tests\test_eval_harness.py
```

RAG retrieval evaluation:

```powershell
.\.conda\python.exe -m app.evals.rag_eval --backend memory
.\.conda\python.exe -m app.evals.rag_eval --backend qdrant
```

The evaluation harness reports metrics such as intent accuracy, tool accuracy, tool
argument accuracy, missing-slot accuracy, forbidden-tool violations, citation hit rate,
groundedness, unsafe request blocking, handoff precision, task success, and latency.

## API Surface

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/chat/stream` | SSE chat stream with agent steps, ActionPlan, citations, tool calls, tokens, and final state. |
| `GET` | `/api/conversations/{conversation_id}` | Conversation snapshot with messages, traces, cases, tasks, and tool calls. |
| `GET` | `/api/conversations/{conversation_id}/stream-state` | Runtime short memory and stream-event state. |
| `GET` | `/api/cases` | Service-case ledger. |
| `GET` | `/api/cases/{case_id}` | Case details, tasks, and tool-audit records. |
| `POST` | `/api/tasks/{task_id}/confirm` | Resume a pending side-effect task after explicit approval. |
| `GET` | `/api/tickets` | Human ticket queue. |
| `PATCH` | `/api/tickets/{ticket_id}` | Update assignment, reply, status, or resolution fields. |
| `POST` | `/api/kb/ingest` | Ingest a knowledge document. |
| `GET` | `/api/kb/search` | Search the knowledge base. |
| `POST` | `/api/evals/run` | Run deterministic agent regression cases. |
| `GET` | `/api/harness/manifest` | Workflow contracts, release gates, and tool metadata. |
| `GET` | `/health` | Runtime backend and provider health. |

## Deployment Notes

The repository includes Dockerfiles for the backend and frontend plus a Compose stack for
local service dependencies.

```powershell
docker compose up --build
```

The Compose stack starts:

- FastAPI backend
- Nginx-served frontend
- PostgreSQL
- Redis
- Qdrant
- Jaeger
- Prometheus
- Grafana

For a public production deployment, replace demo credentials, configure persistent volumes,
restrict CORS, use a secret manager for API keys, and add authentication before exposing
the API.

## Security and Governance

- `.env` files are ignored by Git; `.env.example` contains only safe placeholder values.
- Tool calls are bound to an `AuthContext` and checked by `ToolPolicy`.
- High-risk side effects can require confirmation and idempotency keys.
- Privacy or prompt-injection cases can be blocked or escalated to a human ticket.
- Tool execution writes audit metadata that can be inspected through case and conversation APIs.

## Known Limitations

- The authentication layer is intentionally demo-oriented and should be replaced before production use.
- The default mock LLM is deterministic and useful for tests, but it is not a substitute for live-model evaluation.
- The local deterministic embedding provider is designed for reproducibility, not semantic quality.
- The LangGraph implementation is currently exposed as workflow metadata; the live executor is the explicit orchestrator sequence.
- Seed data is synthetic and optimized for demo coverage rather than business realism.

## Roadmap

- Bind the current workflow contract to a live LangGraph executor.
- Add role-based access control for agent, supervisor, and admin personas.
- Add persistent eval-run storage and trend comparison between prompt/model versions.
- Add richer ticket collaboration features such as internal notes and SLA timers.
- Add deployment manifests for a cloud target.

## License

SmartCS ResolutionOps Console is released under the [MIT License](LICENSE).
