from __future__ import annotations

from typing import Any


def build(settings: Any) -> Any:
    driver = (getattr(settings, "LLM_DRIVER", "") or "null").lower()
    if driver == "null":
        from app.adapters.llm.null import NullLlm
        return NullLlm()
    if driver == "gemini":
        from app.adapters.llm.gemini import GeminiLlm
        return GeminiLlm(
            api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL,
            timeout=settings.GEMINI_TIMEOUT_SECONDS, allowed_tools=settings.llm_tool_allowlist)
    from app.ports.errors import ConfigError
    raise ConfigError(f"unknown llm driver: {driver!r} — allowed: null, gemini")
