from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import utc_now


@dataclass
class KnowledgeFeedback:
    id: str
    query: str
    status: str = "open"
    reason: str = "low_confidence"
    suggested_fix: str = ""
    related_doc_id: str | None = None
    created_at: str = field(default_factory=utc_now)
