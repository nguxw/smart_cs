from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings


class LLMProvider(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return a completed assistant message."""


@dataclass
class MockLLMProvider:
    """Deterministic provider used for local development, tests, and demos without keys."""

    model: str = "mock-smartcs"

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        lower = user_prompt.lower()
        if "json" in system_prompt.lower() and "intent" in lower:
            return json.dumps({"intent": "faq", "confidence": 0.82}, ensure_ascii=False)
        if "refund" in lower or "退款" in user_prompt:
            return "我会先核对订单是否符合退款规则，再给出可执行的下一步。"
        if "invoice" in lower or "发票" in user_prompt:
            return "我会查询发票状态，并在可下载时提供发票入口。"
        if "order" in lower or "订单" in user_prompt or "物流" in user_prompt:
            return "我会查询订单与物流状态，并说明预计处理进度。"
        return "我会基于知识库内容回答，并标注可追溯来源。"


@dataclass
class OpenAICompatibleProvider:
    """Small OpenAI-compatible chat completions client.

    It intentionally uses httpx directly so the project can work with OpenAI-compatible
    gateways without adding SDK-specific coupling.
    """

    api_key: str
    base_url: str
    model: str
    timeout_s: float = 30.0

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        import httpx

        base = self.base_url.rstrip("/")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        return body["choices"][0]["message"]["content"]


@dataclass
class OllamaProvider:
    base_url: str
    model: str
    timeout_s: float = 60.0

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        import httpx

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(f"{self.base_url.rstrip('/')}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        return body.get("message", {}).get("content", "")


def create_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
        )
    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
        )
    return MockLLMProvider(model=settings.llm_model)
