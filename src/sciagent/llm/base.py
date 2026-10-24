from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

Message = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class LLMClient(Protocol):
    model: str

    def chat(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse: ...


def openai_tool_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert registry tool specs to the OpenAI ``tools`` request format."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            },
        }
        for s in specs
    ]
