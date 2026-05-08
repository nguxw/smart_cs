from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

Intent = Literal["faq", "order", "refund", "invoice", "ticket", "handoff", "unknown"]
SSEEventType = Literal["agent_step", "tool_call", "citation", "token", "final", "error"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    created_at: str = field(default_factory=utc_now)


@dataclass
class KnowledgeDoc:
    id: str
    title: str
    content: str
    source: str
    category: str
    tags: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class GuardrailResult:
    passed: bool
    blocked: bool = False
    reason: str = ""
    redacted_text: str = ""
    pii_detected: list[str] = field(default_factory=list)
    requires_human: bool = False


@dataclass
class AgentStep:
    agent: str
    status: Literal["started", "completed", "skipped", "failed"]
    message: str
    elapsed_ms: float = 0.0


@dataclass
class AgentState:
    messages: list[ChatMessage]
    user_profile: dict[str, Any]
    intent: Intent = "unknown"
    retrieved_docs: list[KnowledgeDoc] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    draft_answer: str = ""
    guardrail_result: GuardrailResult | None = None
    final_answer: str = ""
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    conversation_id: str = field(default_factory=lambda: uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamEvent:
    event: SSEEventType
    data: dict[str, Any]

