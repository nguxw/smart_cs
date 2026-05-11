from __future__ import annotations

from enum import Enum
from typing import Any

from app.auth.context import AuthContext
from app.models.schemas import ChatMessage
from app.state_machines.case_state import CaseStatus, CaseWorkflow
from app.state_machines.errors import StateTransitionError


class TicketStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


ALLOWED_TICKET_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.PENDING, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.PENDING: {TicketStatus.OPEN, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED},
    TicketStatus.CLOSED: set(),
}


class TicketWorkflow:
    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self.case_workflow = CaseWorkflow(repository)

    def update(
        self,
        *,
        ticket_id: str,
        payload: dict[str, Any],
        actor: AuthContext,
    ) -> dict[str, Any]:
        current = next(
            (row for row in self.repository.list_tickets() if row["id"] == ticket_id),
            None,
        )
        if current is None:
            raise KeyError(f"Ticket not found: {ticket_id}")
        if "status" in payload and payload["status"] is not None:
            source = TicketStatus(current["status"])
            target = TicketStatus(payload["status"])
            if source != target and target not in ALLOWED_TICKET_TRANSITIONS[source]:
                raise StateTransitionError(f"Illegal ticket transition: {source} -> {target}")
        updated = self.repository.update_ticket(ticket_id, payload)
        if updated is None:
            raise KeyError(f"Ticket not found: {ticket_id}")
        linked_cases = [
            row for row in self.repository.list_cases() if row.get("related_ticket_id") == ticket_id
        ]
        human_reply_changed = bool(
            payload.get("human_reply") and payload.get("human_reply") != current.get("human_reply")
        )
        for linked_case in linked_cases:
            updates: dict[str, Any] = {}
            if "priority" in payload:
                updates["priority"] = updated.get("priority")
            if "category" in payload:
                updates["category"] = updated.get("category")
            if human_reply_changed:
                self.repository.append_message(
                    linked_case["conversation_id"],
                    ChatMessage(role="assistant", content=str(payload["human_reply"])),
                )
                updates["summary"] = str(payload["human_reply"])[:180]
            elif payload.get("agent_summary"):
                updates["summary"] = str(payload["agent_summary"])[:180]
            if updates:
                self.repository.update_case(linked_case["id"], updates)

            if "status" not in payload:
                continue
            target_case_status: CaseStatus | None = None
            if updated.get("status") == TicketStatus.RESOLVED.value:
                target_case_status = CaseStatus.RESOLVED
            elif updated.get("status") == TicketStatus.PENDING.value:
                target_case_status = CaseStatus.WAITING_CUSTOMER
            elif updated.get("status") == TicketStatus.OPEN.value:
                target_case_status = CaseStatus.HANDOFF
            if target_case_status is None:
                continue
            reason = (
                updated.get("closed_reason")
                or updated.get("resolution_type")
                or updated.get("human_reply")
                or updated.get("agent_summary")
                or "ticket_update"
            )
            self.case_workflow.transition(
                case_id=linked_case["id"],
                target=target_case_status,
                reason=reason,
                actor=actor,
                updates={"resolution": reason if target_case_status == CaseStatus.RESOLVED else ""},
                allow_pending_tasks=True,
            )
        return updated
