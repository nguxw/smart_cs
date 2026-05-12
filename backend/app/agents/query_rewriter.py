from __future__ import annotations

import asyncio

from app.llm.provider import LLMProvider


async def rewrite_kb_query(
    message: str,
    intent: str,
    llm: LLMProvider,
    timeout_s: float = 3.0,
) -> str:
    """Rewrite a user turn into a compact knowledge-base search query."""

    system_prompt = (
        "You rewrite ecommerce after-sales support questions into short knowledge-base "
        "search queries. Return only the query text. Do not explain."
    )
    user_prompt = f"Intent: {intent}\nUser message: {message}\nSearch query:"

    try:
        query = await asyncio.wait_for(llm.complete(system_prompt, user_prompt), timeout=timeout_s)
    except Exception:
        return message

    query = _clean_query(query)
    if 2 <= len(query) <= 80:
        return query
    return message


def _clean_query(query: str) -> str:
    cleaned = query.strip().strip("`\"'")
    return " ".join(line.strip() for line in cleaned.splitlines() if line.strip())
