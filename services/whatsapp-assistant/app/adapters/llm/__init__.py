from __future__ import annotations

from typing import Any


def build(settings: Any, *, secret_store: Any = None, runtime_config: Any = None) -> Any:
    driver = (getattr(settings, "LLM_DRIVER", "") or "null").lower()
    if driver == "null":
        from app.adapters.llm.null import NullLlm
        return NullLlm()
    if driver == "assistant_service":
        from app.adapters.llm.assistant_service import AssistantServiceLlm
        from app.core.assistant_connections import HttpAssistantConnections
        connections = HttpAssistantConnections(
            url=settings.ASSISTANT_SERVICE_URL, connections_path=settings.ASSISTANT_SERVICE_CONNECTIONS_PATH,
            token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.ASSISTANT_SERVICE_TIMEOUT_SECONDS)
        # `secret_store` lets an operator set/rotate ASSISTANT_MODEL_PROJECT/ASSISTANT_MODEL_
        # CREDENTIAL from the panel without a redeploy (app/api/v1/operator.py) — settings' own
        # env values stay the fallback underneath it, so a deployment with nothing stored yet
        # behaves exactly as configured.
        return AssistantServiceLlm(
            connections=connections, model_location=settings.ASSISTANT_MODEL_LOCATION,
            model_name=settings.ASSISTANT_MODEL_NAME, model_auth=settings.ASSISTANT_MODEL_AUTH,
            env_project=settings.ASSISTANT_MODEL_PROJECT, env_credential=settings.ASSISTANT_MODEL_CREDENTIAL,
            allowed_tools=settings.llm_tool_allowlist, secret_store=secret_store,
            runtime_config=runtime_config, max_reply_tokens=settings.MAX_REPLY_TOKENS)
    from app.ports.errors import ConfigError
    raise ConfigError(f"unknown llm driver: {driver!r} — allowed: null, assistant_service")
