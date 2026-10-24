"""Tool registry with schema validation.

A :class:`Tool` couples a typed pydantic input model with a pure function. The
same registry backs the in-process gateway and the MCP servers, so a tool is
defined exactly once regardless of transport.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from sciagent.core.errors import NotFoundError, ToolExecutionError, ValidationFailed
from sciagent.core.telemetry import TOOL_CALLS, TOOL_LATENCY


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    server: str  # imaging | genomics | clinical
    input_model: type[BaseModel]
    fn: Callable[[Any], dict[str, Any]]

    def json_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "server": self.server,
            "input_schema": self.json_schema(),
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise NotFoundError("unknown tool", tool=name) from None

    def names(self) -> list[str]:
        return sorted(self._tools)

    def by_server(self, server: str) -> list[Tool]:
        return [t for t in self._tools.values() if t.server == server]

    def specs(self) -> list[dict[str, Any]]:
        return [self._tools[n].spec() for n in self.names()]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        try:
            params = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            TOOL_CALLS.labels(name, "invalid").inc()
            raise ValidationFailed(
                "invalid tool arguments", tool=name, errors=exc.errors()
            ) from exc
        start = time.perf_counter()
        try:
            result = tool.fn(params)
        except Exception as exc:
            TOOL_CALLS.labels(name, "error").inc()
            raise ToolExecutionError(f"{name} failed: {exc}", tool=name) from exc
        finally:
            TOOL_LATENCY.labels(name).observe(time.perf_counter() - start)
        TOOL_CALLS.labels(name, "ok").inc()
        return result


def default_registry() -> ToolRegistry:
    from sciagent.tools import clinical, genomics, imaging

    registry = ToolRegistry()
    for module in (imaging, genomics, clinical):
        for tool in module.TOOLS:
            registry.register(tool)
    return registry
