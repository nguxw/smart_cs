from __future__ import annotations


class StateTransitionError(ValueError):
    """Raised when a case, task, or ticket transition violates workflow rules."""
