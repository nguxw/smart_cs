from __future__ import annotations

from enum import Enum
from typing import Any

from app.auth.context import AuthContext
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
        if updated.get("status") == TicketStatus.RESOLVED.value:
            linked_case = next(
                (
                    row
                    for row in self.repository.list_cases()
                    if row.get("related_ticket_id") == ticket_id
                ),
                None,
            )
            if linked_case and linked_case.get("status") == CaseStatus.HANDOFF.value:
                reason = (
                    updated.get("closed_reason")
                    or updated.get("resolution_type")
                    or updated.get("human_reply")
                    or "ticket_resolved"
                )
                self.case_workflow.transition(
                    case_id=linked_case["id"],
                    target=CaseStatus.RESOLVED,
                    reason=reason,
                    actor=actor,
                    updates={"resolution": reason},
                    allow_pending_tasks=True,
                )
        return updated
