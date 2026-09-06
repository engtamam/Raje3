"""NullLlm — proposes nothing, replies with a fixed sentence. Refused in production
(config.py::assert_llm_config_ok) because a receptionist that never answers is the quietest outage
this service can produce, exactly the same shape as reminders' NullSender."""
from __future__ import annotations

from app.ports.llm import LlmReply


class NullLlm:
    driver = "null"

    async def respond(self, *, system_prompt: str, summary: str, recent_messages: list[dict],
                      user_message: str, allowed_tools: frozenset[str],
                      context_block: str = "", tenant: str = "") -> LlmReply:
        return LlmReply(text="", input_tokens=0, output_tokens=0)
