from __future__ import annotations

from typing import Any

from app.auth.context import AuthContext
from app.auth.dependencies import require_case_access


class TraceService:
    def __init__(self, repository: Any, runtime_service: Any) -> None:
        self.repository = repository
        self.runtime_service = runtime_service

    def get_trace(self, trace_id: str, auth: AuthContext) -> dict[str, Any] | None:
        if hasattr(self.repository, "_connect"):
            return self._postgres_trace(trace_id, auth)
        return self._memory_trace(trace_id, auth)

    def _memory_trace(self, trace_id: str, auth: AuthContext) -> dict[str, Any] | None:
        conversations = getattr(self.repository, "conversations", {})
        for conversation in conversations.values():
            if trace_id not in conversation.trace_ids:
                continue
            snapshot = self.repository.conversation_snapshot(conversation.id)
            if snapshot is None:
                return None
            case = next(
                (
                    row
                    for row in snapshot.get("cases", [])
                    if trace_id in snapshot["trace_ids"]
                ),
                None,
            )
            if case:
                require_case_access(case, auth)
            return self._shape_trace(trace_id, snapshot, case)
        return None

    def _postgres_trace(self, trace_id: str, auth: AuthContext) -> dict[str, Any] | None:
        with self.repository._connect() as conn:
            trace_row = conn.execute(
                """
                SELECT conversation_id, trace_id, created_at
                FROM conversation_traces
                WHERE trace_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (trace_id,),
            ).fetchone()
            if trace_row is None:
                return None
            snapshot = self.repository.conversation_snapshot(trace_row["conversation_id"])
        if snapshot is None:
            return None
        case = next(
            (
                row
                for row in snapshot.get("cases", [])
                if row.get("conversation_id") == snapshot["id"]
            ),
            None,
        )
        if case:
            require_case_access(case, auth)
        return self._shape_trace(trace_id, snapshot, case)

    def _shape_trace(
        self,
        trace_id: str,
        snapshot: dict[str, Any],
        case: dict[str, Any] | None,
    ) -> dict[str, Any]:
        steps = [
            row
            for row in snapshot.get("agent_steps", [])
            if not row.get("trace_id") or row.get("trace_id") == trace_id
        ]
        tool_calls = [
            row
            for row in snapshot.get("tool_calls", [])
            if not row.get("trace_id") or row.get("trace_id") == trace_id
        ]
        stream_events = self.runtime_service.latest_stream_events(snapshot["id"])
        citations = [
            event.get("data", {})
            for event in stream_events
            if event.get("event") == "citation"
        ]
        final_events = [
            event.get("data", {})
            for event in stream_events
            if event.get("event") == "final"
        ]
        final = final_events[-1] if final_events else {}
        return {
            "trace_id": trace_id,
            "conversation_id": snapshot["id"],
            "case_id": (case or {}).get("id"),
            "task_id": (case or {}).get("current_task_id"),
            "graph_path": [step.get("agent") for step in steps],
            "node_latencies": {
                str(step.get("agent")): step.get("elapsed_ms", 0)
                for step in steps
                if step.get("status") == "completed"
            },
            "retrieved_docs": citations,
            "tool_policy_decisions": [
                {
                    "name": call.get("name"),
                    "policy_status": call.get("policy_status"),
                    "success": call.get("success"),
                    "error": call.get("error"),
                }
                for call in tool_calls
            ],
            "tool_calls": tool_calls,
            "guardrail": final.get("guardrail"),
            "final_answer": final.get("answer") or snapshot.get("summary", ""),
        }
