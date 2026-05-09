from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import utc_now


@dataclass
class KnowledgeDocumentVersion:
    id: str
    source: str
    version: int
    status: str = "draft"
    reviewer: str | None = None
    change_note: str = ""
    created_at: str = field(default_factory=utc_now)
