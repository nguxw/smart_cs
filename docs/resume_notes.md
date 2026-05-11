# Resume Notes

Built a full-stack AI customer support operations console for e-commerce after-sales scenarios.
The backend uses FastAPI and an explicit orchestrator sequence, with a LangGraph migration
contract exposed as metadata, to coordinate routing, ActionPlan generation, RAG retrieval,
governed business tools, human confirmation, guardrail review, memory writing, and streaming
answer composition.

The project includes service-case tracking, customer confirmation tasks, tool risk governance,
idempotent tool audits, deterministic local evals, RAG retrieval evals, and a React console that
shows the Agent execution timeline, ActionPlan, citations, tool traces, and business outcomes.
