# SmartCS Backend

FastAPI backend for the SmartCS ResolutionOps Console.

The backend owns the agent orchestrator, ActionPlan generation, RAG retrieval,
business tool policy runtime, service-case ledger, human confirmation tasks,
ticket APIs, knowledge APIs, and deterministic evaluation harness.

Common local commands:

```powershell
.\.conda\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000
.\.conda\python.exe -m pytest backend
.\.conda\python.exe -m ruff check backend\app backend\tests
```

See the root [README](../README.md) for the full product overview and setup guide.
