# SmartCS Agent Desk Architecture

## Runtime Flow

```mermaid
flowchart LR
  U["User"] --> FE["React Agent Desk"]
  FE --> API["FastAPI SSE API"]
  API --> R["router"]
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

The eval harness replays categorized e-commerce cases through the same orchestrator used by the API. It records intent accuracy, tool selection, tool argument correctness, citation hit rate, groundedness, handoff precision, task success, PII leakage, unsafe-request blocking, and latency. The default run uses `MockLLMProvider` to keep CI deterministic and free.

## Production Swap Points

- `LLMProvider`: switch `LLM_PROVIDER=openai-compatible` and set `OPENAI_API_KEY`, `OPENAI_API_BASE`, `MODEL_NAME`.
- `PostgresRepository`: stores users, orders, refunds, tickets, cases, tasks, tool audits, conversations, messages, agent steps, tool calls, and trace IDs.
- `RedisRuntimeService`: stores short-term memory, stream events, and rate-limit counters.
- `QdrantKnowledgeStore`: stores seeded and manually ingested knowledge chunks as vectors with metadata filters, reranking, and grounding metadata.
- `ToolRuntime`: wraps `BusinessToolRegistry` with AuthContext binding, ToolPolicy, confirmation, idempotency, and audit.
