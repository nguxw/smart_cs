from __future__ import annotations

from typing import Any

from app.tools.business_tools import BusinessToolRegistry


def create_fastmcp_server(registry: BusinessToolRegistry) -> Any:
    """Create an optional FastMCP server from the in-process business registry.

    The API uses the in-process registry for low-latency demos. This adapter exists so the same
    tool surface can be exposed through MCP in production or inspected during interviews.
    """

    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - optional dependency boundary
        raise RuntimeError("Install the mcp package to enable FastMCP server mode") from exc

    server = FastMCP("smartcs-tools")

    @server.tool()
    async def query_order(order_id: str, user_id: str) -> dict[str, Any]:
        """查询当前用户名下订单、物流、金额和发票状态。"""

        return registry.repository.query_order(order_id, user_id)

    @server.tool()
    async def check_refund_eligibility(order_id: str, user_id: str) -> dict[str, Any]:
        """检查订单是否符合自助退款规则。"""

        return registry.repository.check_refund_eligibility(order_id, user_id)

    @server.tool()
    async def create_refund(order_id: str, user_id: str, reason: str) -> dict[str, Any]:
        """创建退款申请。"""

        return registry.repository.create_refund(order_id, user_id, reason)

    @server.tool()
    async def query_invoice(order_id: str, user_id: str) -> dict[str, Any]:
        """查询订单发票状态和下载地址。"""

        return registry.repository.query_invoice(order_id, user_id)

    @server.tool()
    async def create_ticket(
        user_id: str,
        title: str,
        description: str,
        priority: str = "medium",
        category: str = "general",
    ) -> dict[str, Any]:
        """创建人工客服工单。"""

        return registry.repository.create_ticket(user_id, title, description, priority, category)

    @server.tool()
    async def handoff_to_human(user_id: str, reason: str, conversation_id: str) -> dict[str, Any]:
        """将敏感或复杂问题移交人工客服。"""

        return registry.repository.create_ticket(
            user_id=user_id,
            title="人工客服介入",
            description=f"会话 {conversation_id} 需要人工处理：{reason}",
            priority="high",
            category="handoff",
        )

    return server

