"""StubLlm — a scriptable fake for integration tests.

NOT wired into adapters/llm/build() and not selectable by LLM_DRIVER — a stub that could be
selected by config could also be selected in production, which is precisely the class of "test-only
code reachable from a real deployment" this platform's tests guard against elsewhere. Tests import
this directly and hand it to a Container by construction.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from app.ports.llm import LlmReply, ToolCall


class StubLlm:
    driver = "stub"

    def __init__(self, scripted: list[LlmReply] | None = None) -> None:
        self._queue: deque[LlmReply] = deque(scripted or [])
        self.calls: list[dict[str, Any]] = []

    def queue(self, reply: LlmReply) -> None:
        self._queue.append(reply)

    def queue_tool_call(self, name: str, **args: Any) -> None:
        self._queue.append(LlmReply(tool_call=ToolCall(name=name, args=args),
                                    input_tokens=10, output_tokens=5))

    def queue_text(self, text: str) -> None:
        self._queue.append(LlmReply(text=text, input_tokens=10, output_tokens=5))

    async def respond(self, *, system_prompt: str, summary: str, recent_messages: list[dict],
                      user_message: str, allowed_tools: frozenset[str],
                      context_block: str = "") -> LlmReply:
        self.calls.append({"system_prompt": system_prompt, "summary": summary,
                           "recent_messages": recent_messages, "user_message": user_message,
                           "allowed_tools": allowed_tools, "context_block": context_block})
        if self._queue:
            return self._queue.popleft()
        return LlmReply(text="عذرًا، لم أفهم طلبك.", input_tokens=5, output_tokens=5)
