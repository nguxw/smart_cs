from __future__ import annotations

from enum import Enum
from typing import Any

from app.auth.context import AuthContext
from app.state_machines.errors import StateTransitionError


class CaseStatus(str, Enum):
    OPEN = "open"
    WAITING_CUSTOMER = "waiting_customer"
    PROCESSING = "processing"
    HANDOFF = "handoff"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


ALLOWED_CASE_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.OPEN: {
        CaseStatus.WAITING_CUSTOMER,
        CaseStatus.PROCESSING,
        CaseStatus.HANDOFF,
        CaseStatus.RESOLVED,
        CaseStatus.CANCELLED,
    },
    CaseStatus.WAITING_CUSTOMER: {
        CaseStatus.PROCESSING,
        CaseStatus.OPEN,
        CaseStatus.RESOLVED,
        CaseStatus.CANCELLED,
    },
    CaseStatus.PROCESSING: {
        CaseStatus.WAITING_CUSTOMER,
        CaseStatus.HANDOFF,
        CaseStatus.RESOLVED,
    },
    CaseStatus.HANDOFF: {
        CaseStatus.WAITING_CUSTOMER,
        CaseStatus.OPEN,
        CaseStatus.RESOLVED,
    },
    CaseStatus.RESOLVED: {CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
    CaseStatus.CANCELLED: set(),
}


class CaseWorkflow:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def transition(
        self,
        *,
        case_id: str,
        target: CaseStatus | str,
        reason: str,
        actor: AuthContext,
        updates: dict[str, Any] | None = None,
        allow_pending_tasks: bool = False,
    ) -> dict[str, Any]:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(f"Case not found: {case_id}")
        current = CaseStatus(case["status"])
        target_status = CaseStatus(target)
        if current == target_status:
            payload = dict(updates or {})
            payload.setdefault("summary", reason)
            return self.repository.update_case(case_id, payload) or case
        if target_status not in ALLOWED_CASE_TRANSITIONS[current]:
            raise StateTransitionError(f"Illegal case transition: {current} -> {target_status}")
        if target_status in {CaseStatus.RESOLVED, CaseStatus.CLOSED} and not allow_pending_tasks:
            pending_tasks = self.repository.list_tasks(case_id=case_id, status="pending")
            if pending_tasks:
                raise StateTransitionError("Cannot resolve or close a case with pending tasks")
        if current == CaseStatus.HANDOFF and target_status == CaseStatus.RESOLVED:
            ticket_id = case.get("related_ticket_id")
            tickets = self.repository.list_tickets()
            ticket = next((row for row in tickets if row.get("id") == ticket_id), None)
            if not ticket or ticket.get("status") != "resolved":
                raise StateTransitionError(
                    "Handoff cases require a resolved ticket before resolution"
                )
        payload = dict(updates or {})
        payload["status"] = target_status.value
        terminal_statuses = {CaseStatus.RESOLVED, CaseStatus.CLOSED, CaseStatus.CANCELLED}
        if reason and target_status in terminal_statuses:
            payload.setdefault("resolution", reason)
        payload.setdefault("summary", reason)
        payload["transition_actor"] = actor.user_id
        payload["transition_reason"] = reason
        return self.repository.update_case(case_id, payload) or case
