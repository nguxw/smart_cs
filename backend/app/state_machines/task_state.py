from __future__ import annotations

from enum import Enum
from typing import Any

from app.auth.context import AuthContext
from app.state_machines.case_state import CaseStatus, CaseWorkflow
from app.state_machines.errors import StateTransitionError


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


ALLOWED_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.FAILED: set(),
}


class TaskWorkflow:
    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self.case_workflow = CaseWorkflow(repository)

    def create_confirmation(
        self,
        *,
        case_id: str,
        required_action: str,
        pending_confirmation: dict[str, Any],
        actor: AuthContext,
    ) -> dict[str, Any]:
        task = self.repository.create_task(
            case_id=case_id,
            task_type="customer_confirmation",
            required_action=required_action,
            pending_confirmation=pending_confirmation,
        )
        self.case_workflow.transition(
            case_id=case_id,
            target=CaseStatus.WAITING_CUSTOMER,
            reason="waiting_for_customer_confirmation",
            actor=actor,
            updates={"current_task_id": task["id"]},
            allow_pending_tasks=True,
        )
        return task

    def transition(
        self,
        *,
        task_id: str,
        target: TaskStatus | str,
        reason: str,
        actor: AuthContext,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        current = TaskStatus(task["status"])
        target_status = TaskStatus(target)
        if current == target_status:
            return task
        if target_status not in ALLOWED_TASK_TRANSITIONS[current]:
            raise StateTransitionError(f"Illegal task transition: {current} -> {target_status}")
        updated = self.repository.update_task(
            task_id,
            {
                "status": target_status.value,
                "result": {
                    **(result or {}),
                    "transition_reason": reason,
                    "transition_actor": actor.user_id,
                },
            },
        )
        case = self.repository.get_case(task["case_id"])
        terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED}
        if case and target_status in terminal_statuses:
            self.repository.update_case(case["id"], {"current_task_id": None})
        if case and target_status in {TaskStatus.CANCELLED, TaskStatus.FAILED}:
            self.case_workflow.transition(
                case_id=case["id"],
                target=CaseStatus.OPEN,
                reason=reason,
                actor=actor,
                updates={"current_task_id": None},
                allow_pending_tasks=True,
            )
        return updated or task
