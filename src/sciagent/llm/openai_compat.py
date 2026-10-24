"""Client for vLLM's OpenAI-compatible ``/v1/chat/completions`` endpoint."""

from __future__ import annotations

import json
from typing import Any

import httpx

from sciagent.core.errors import SciAgentError
from sciagent.llm.base import LLMResponse, Message, ToolCall, Usage, openai_tool_specs


class LLMUnavailable(SciAgentError):
    status_code = 503
    code = "llm_unavailable"


class OpenAICompatibleLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_s: float = 30.0,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._http = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)

    def chat(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = openai_tool_specs(tools)
            body["tool_choice"] = "auto"
        try:
            resp = self._http.post("/chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"LLM request failed: {exc}") from exc
        data = resp.json()
        msg = data["choices"][0]["message"]
        calls = [
            ToolCall(
                id=c["id"],
                name=c["function"]["name"],
                arguments=_parse_args(c["function"].get("arguments")),
            )
            for c in msg.get("tool_calls") or []
        ]
        usage = data.get("usage") or {}
        return LLMResponse(
            content=msg.get("content"),
            tool_calls=calls,
            usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
        )


def _parse_args(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}
    return parsed if isinstance(parsed, dict) else {"_raw": parsed}
