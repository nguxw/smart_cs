from __future__ import annotations

import re

from app.models.schemas import GuardrailResult

PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
BANK_CARD_RE = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")

PROMPT_INJECTION_PATTERNS = [
    "忽略之前",
    "忽略所有",
    "系统提示",
    "system prompt",
    "developer message",
    "泄露",
    "api key",
    "密钥",
    "越权",
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    detected: list[str] = []

    def _sub(pattern: re.Pattern[str], label: str, value: str) -> str:
        nonlocal detected
        if pattern.search(value):
            detected.append(label)
        return pattern.sub(f"[REDACTED_{label}]", value)

    redacted = text
    redacted = _sub(PHONE_RE, "PHONE", redacted)
    redacted = _sub(ID_CARD_RE, "ID_CARD", redacted)
    redacted = _sub(BANK_CARD_RE, "BANK_CARD", redacted)
    redacted = _sub(EMAIL_RE, "EMAIL", redacted)
    return redacted, sorted(set(detected))


def check_input_safety(text: str) -> GuardrailResult:
    redacted, pii = redact_pii(text)
    lower = text.lower()
    if any(pattern.lower() in lower for pattern in PROMPT_INJECTION_PATTERNS):
        return GuardrailResult(
            passed=False,
            blocked=True,
            reason="检测到提示词注入或越权请求",
            redacted_text=redacted,
            pii_detected=pii,
            requires_human=True,
        )
    return GuardrailResult(
        passed=True,
        blocked=False,
        reason="input_safe",
        redacted_text=redacted,
        pii_detected=pii,
    )


def check_output_safety(text: str) -> GuardrailResult:
    redacted, pii = redact_pii(text)
    return GuardrailResult(
        passed=True,
        blocked=False,
        reason="output_redacted" if pii else "output_safe",
        redacted_text=redacted,
        pii_detected=pii,
    )

