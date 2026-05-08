from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.models.schemas import ToolCallRecord

ToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    category: str


class BusinessToolRegistry:
    """MCP-style tool registry used by agents and exposed by the API."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self._tools: dict[str, tuple[ToolDefinition, Callable[..., Any]]] = {}
        self._register_defaults()

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Any],
    ) -> None:
        self._tools[definition.name] = (definition, handler)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "inputSchema": definition.input_schema,
                "category": definition.category,
            }
            for definition, _ in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallRecord:
        start = time.perf_counter()
        definition_handler = self._tools.get(name)
        if definition_handler is None:
            return ToolCallRecord(
                name=name,
                arguments=arguments,
                success=False,
                error=f"Tool not found: {name}",
            )
        _, handler = definition_handler
        try:
            result = handler(**arguments)
            if inspect.isawaitable(result):
                result = await result
            return ToolCallRecord(
                name=name,
                arguments=arguments,
                success=True,
                result=result,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:  # pragma: no cover - defensive boundary
            return ToolCallRecord(
                name=name,
                arguments=arguments,
                success=False,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _register_defaults(self) -> None:
        self.register(
            ToolDefinition(
                name="query_order",
                description="查询当前用户名下订单、物流、金额和发票状态",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                    },
                    "required": ["order_id", "user_id"],
                },
                category="order",
            ),
            self.repository.query_order,
        )
        self.register(
            ToolDefinition(
                name="check_refund_eligibility",
                description="检查订单是否符合自助退款规则",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                    },
                    "required": ["order_id", "user_id"],
                },
                category="refund",
            ),
            self.repository.check_refund_eligibility,
        )
        self.register(
            ToolDefinition(
                name="create_refund",
                description="创建退款申请",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["order_id", "user_id", "reason"],
                },
                category="refund",
            ),
            self.repository.create_refund,
        )
        self.register(
            ToolDefinition(
                name="query_invoice",
                description="查询订单发票状态和下载地址",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                    },
                    "required": ["order_id", "user_id"],
                },
                category="invoice",
            ),
            self.repository.query_invoice,
        )
        self.register(
            ToolDefinition(
                name="create_ticket",
                description="创建人工客服工单",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["user_id", "title", "description"],
                },
                category="ticket",
            ),
            self.repository.create_ticket,
        )
        self.register(
            ToolDefinition(
                name="handoff_to_human",
                description="将敏感或复杂问题移交人工客服",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "reason": {"type": "string"},
                        "conversation_id": {"type": "string"},
                    },
                    "required": ["user_id", "reason", "conversation_id"],
                },
                category="ticket",
            ),
            self._handoff_to_human,
        )

    def _handoff_to_human(self, user_id: str, reason: str, conversation_id: str) -> dict[str, Any]:
        return self.repository.create_ticket(
            user_id=user_id,
            title="人工客服介入",
            description=f"会话 {conversation_id} 需要人工处理：{reason}",
            priority="high",
            category="handoff",
        )
