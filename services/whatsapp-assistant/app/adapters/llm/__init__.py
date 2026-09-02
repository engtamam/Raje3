from __future__ import annotations

from typing import Any


def build(settings: Any, *, secret_store: Any = None) -> Any:
    driver = (getattr(settings, "LLM_DRIVER", "") or "null").lower()
    if driver == "null":
        from app.adapters.llm.null import NullLlm
        return NullLlm()
    if driver == "gemini":
        from app.adapters.llm.gemini import GeminiLlm
        # `secret_store` lets an operator rotate GEMINI_API_KEY from the panel without a redeploy
        # (app/api/v1/operator.py) — settings.GEMINI_API_KEY stays the env fallback underneath it,
        # so a deployment with nothing stored behaves exactly as before.
        return GeminiLlm(
            api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL,
            timeout=settings.GEMINI_TIMEOUT_SECONDS, allowed_tools=settings.llm_tool_allowlist,
            secret_store=secret_store)
    from app.ports.errors import ConfigError
    raise ConfigError(f"unknown llm driver: {driver!r} — allowed: null, gemini")
