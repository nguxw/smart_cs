from __future__ import annotations

import pytest

from app.auth.context import AuthContext
from app.data.repository import DemoRepository
from app.state_machines import (
    CaseStatus,
    CaseWorkflow,
    TaskStatus,
    TaskWorkflow,
    TicketWorkflow,
)
from app.state_machines.errors import StateTransitionError


def test_case_valid_transitions() -> None:
    repo = DemoRepository()
    actor = AuthContext(user_id="u_1001")
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-1", "refund")
    workflow = CaseWorkflow(repo)

    waiting = workflow.transition(
        case_id=case["id"],
        target=CaseStatus.WAITING_CUSTOMER,
        reason="needs customer confirmation",
        actor=actor,
    )
    assert waiting["status"] == "waiting_customer"

    processing = workflow.transition(
        case_id=case["id"],
        target=CaseStatus.PROCESSING,
        reason="customer confirmed",
        actor=actor,
    )
    assert processing["status"] == "processing"


def test_resolved_case_cannot_reopen_to_processing() -> None:
    repo = DemoRepository()
    actor = AuthContext(user_id="u_1001")
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-2", "refund")
    workflow = CaseWorkflow(repo)

    workflow.transition(
        case_id=case["id"],
        target=CaseStatus.RESOLVED,
        reason="done",
        actor=actor,
    )
    with pytest.raises(StateTransitionError):
        workflow.transition(
            case_id=case["id"],
            target=CaseStatus.PROCESSING,
            reason="illegal reopen",
            actor=actor,
        )


def test_closed_case_cannot_reopen() -> None:
    repo = DemoRepository()
    actor = AuthContext(user_id="u_1001")
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-3", "refund")
    workflow = CaseWorkflow(repo)

    workflow.transition(
        case_id=case["id"],
        target=CaseStatus.RESOLVED,
        reason="done",
        actor=actor,
    )
    workflow.transition(
        case_id=case["id"],
        target=CaseStatus.CLOSED,
        reason="archived",
        actor=actor,
    )
    with pytest.raises(StateTransitionError):
        workflow.transition(
            case_id=case["id"],
            target=CaseStatus.OPEN,
            reason="reopen",
            actor=actor,
        )


def test_handoff_case_requires_resolved_ticket_before_resolution() -> None:
    repo = DemoRepository()
    actor = AuthContext(user_id="u_1001")
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-4", "ticket")
    ticket = repo.create_ticket("u_1001", "Needs agent", "handoff")
    workflow = CaseWorkflow(repo)

    repo.update_case(case["id"], {"related_ticket_id": ticket["id"]})
    workflow.transition(
        case_id=case["id"],
        target=CaseStatus.HANDOFF,
        reason="agent needed",
        actor=actor,
    )
    with pytest.raises(StateTransitionError):
        workflow.transition(
            case_id=case["id"],
            target=CaseStatus.RESOLVED,
            reason="not resolved yet",
            actor=actor,
        )


def test_pending_task_blocks_case_resolution_until_cancelled() -> None:
    repo = DemoRepository()
    actor = AuthContext(user_id="u_1001")
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-5", "refund")
    task = repo.create_task(case["id"], "customer_confirmation", "confirm_refund")
    case_workflow = CaseWorkflow(repo)
    task_workflow = TaskWorkflow(repo)

    with pytest.raises(StateTransitionError):
        case_workflow.transition(
            case_id=case["id"],
            target=CaseStatus.RESOLVED,
            reason="done",
            actor=actor,
        )

    task_workflow.transition(
        task_id=task["id"],
        target=TaskStatus.CANCELLED,
        reason="customer_cancelled",
        actor=actor,
    )
    resolved = case_workflow.transition(
        case_id=case["id"],
        target=CaseStatus.RESOLVED,
        reason="done after cancel",
        actor=actor,
    )
    assert resolved["status"] == "resolved"


def test_repository_task_update_does_not_mutate_case_status_directly() -> None:
    repo = DemoRepository()
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-6", "refund")
    task = repo.create_task(case["id"], "customer_confirmation", "confirm_refund")

    repo.update_task(task["id"], {"status": "cancelled"})
    unchanged = repo.get_case(case["id"])

    assert unchanged is not None
    assert unchanged["status"] == "open"
    assert unchanged["current_task_id"] is None


def test_ticket_workflow_owns_case_status_sync() -> None:
    repo = DemoRepository()
    actor = AuthContext(user_id="agent-demo")
    case = repo.create_or_get_case("u_1001", "demo-tenant", "cv-state-7", "handoff")
    ticket = repo.create_ticket("u_1001", "Needs agent", "handoff")
    repo.update_case(case["id"], {"related_ticket_id": ticket["id"]})

    repo.update_ticket(ticket["id"], {"status": "pending"})
    direct_case = repo.get_case(case["id"])
    assert direct_case is not None
    assert direct_case["status"] == "open"

    updated_ticket = TicketWorkflow(repo).update(
        ticket_id=ticket["id"],
        payload={"status": "pending"},
        actor=actor,
    )
    synced_case = repo.get_case(case["id"])

    assert updated_ticket["status"] == "pending"
    assert synced_case is not None
    assert synced_case["status"] == "waiting_customer"
