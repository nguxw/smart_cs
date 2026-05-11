from __future__ import annotations

from collections.abc import AsyncIterator

from app.models.schemas import StreamEvent


async def passthrough_stream(events: AsyncIterator[StreamEvent]) -> AsyncIterator[StreamEvent]:
    async for event in events:
        yield event
