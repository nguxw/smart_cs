# SmartCS Agent Desk Architecture

## Runtime Flow

```mermaid
flowchart LR
  U["User"] --> FE["React Agent Desk"]
  FE --> API["FastAPI SSE API"]
  API --> LG["Live LangGraph StateGraph"]
  LG --> R["router"]
  R --> P["input_policy"]
  P --> AP["action_planner"]
  AP --> C["case_binding"]
  C --> K["retrieve_policy"]
  K --> O["tool_policy"]
  O --> H["human_confirm / interrupt"]
  O --> T["human_handoff"]
  H --> G["guardrail"]
  T --> G
  G --> CA["compose_answer"]
  CA --> M["memory_writer"]
  K --> Q["Qdrant Vector Store"]
  O --> TR["ToolRuntime + ToolPolicy + Audit"]
  TR --> MCP["MCP Business Tools"]
  MCP --> DB["PostgreSQL Repository"]
  API --> RDS["Redis Runtime"]
```

## Agent Harness

The eval harness replays categorized e-commerce cases through the default live LangGraph runtime. It records intent accuracy, tool selection, tool argument correctness, citation hit rate, groundedness, handoff precision, task success, PII leakage, unsafe-request blocking, and latency. The default run uses `MockLLMProvider` to keep CI deterministic and free.

## Production Swap Points

- `LLMProvider`: switch `LLM_PROVIDER=openai-compatible` and set `OPENAI_API_KEY`, `OPENAI_API_BASE`, `MODEL_NAME`.
- `PostgresRepository`: stores users, orders, refunds, tickets, cases, tasks, tool audits, conversations, messages, agent steps, tool calls, and trace IDs.
- `RedisRuntimeService`: stores short-term memory, stream events, and rate-limit counters.
- `QdrantKnowledgeStore`: stores seeded and manually ingested knowledge chunks as vectors with metadata filters, reranking, and grounding metadata.
- `ToolRuntime`: wraps `BusinessToolRegistry` with AuthContext binding, ToolPolicy, confirmation, idempotency, and audit.

## Design Decisions

### ADR-001: Live LangGraph With Rule-First Governance

SmartCS now executes the customer-service flow through a live LangGraph `StateGraph`, while preserving bounded node handlers and the existing SSE event contract. Routing, tool selection, risk boundaries, and side effects remain deterministic so the runtime is auditable and regression-tested. The explicit orchestrator remains as a compatibility executor and parity baseline.

### ADR-002: Side Effects Require Confirmation And Idempotency

Read tools can execute directly, while side-effect tools such as refund creation and handoff are wrapped by `ToolPolicy`, confirmation tasks, idempotency keys, and tool audit logs. This makes retry and resume behavior inspectable.

### ADR-003: Deterministic Mock Mode Is A Release Gate

CI uses the mock provider and 51 fixed JSONL fixtures so prompt, tool, and KB regressions are reproducible without model keys. Live-model evaluation is a later comparison layer, not the baseline gate.

### ADR-004: Infrastructure Adapters Are Optional

PostgreSQL, Redis, and Qdrant adapters are production-style swap points. The in-memory fallbacks keep local review fast, while integration tests prove the real service adapters cooperate when containers are available.
