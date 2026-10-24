"""Tool gateways: how the agent reaches tools.

``LocalToolGateway`` calls the registry in-process (tests, notebooks, single-node
deployments). ``McpToolGateway`` calls the per-domain MCP servers over
Streamable HTTP, which is how the platform runs on Kubernetes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from sciagent.core.errors import NotFoundError, ToolExecutionError
from sciagent.tools.registry import ToolRegistry


class ToolGateway(Protocol):
    def specs(self) -> list[dict[str, Any]]: ...

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class LocalToolGateway:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def specs(self) -> list[dict[str, Any]]:
        return self.registry.specs()

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.registry.call(name, arguments)


class McpToolGateway:
    """Route each tool to the MCP server of its domain.

    ``servers`` maps a domain to either a Streamable-HTTP URL or, in tests, an
    in-process :class:`MCPServer`. Tool specs come from the shared registry so the
    agent can plan without a network round-trip.
    """

    def __init__(self, registry: ToolRegistry, servers: dict[str, str | MCPServer]) -> None:
        self.registry = registry
        self.servers = servers

    def specs(self) -> list[dict[str, Any]]:
        return [s for s in self.registry.specs() if s["server"] in self.servers]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.registry.get(name)
        target = self.servers.get(tool.server)
        if target is None:
            raise NotFoundError("no MCP server configured for domain", server=tool.server)
        return asyncio.run(self._call(target, name, arguments))

    @staticmethod
    async def _call(
        target: str | MCPServer, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        async with Client(target, read_timeout_seconds=60) as client:
            result = await client.call_tool(name, arguments)
        text = "".join(getattr(c, "text", "") for c in result.content)
        if result.is_error:
            raise ToolExecutionError(text or f"{name} failed", tool=name)
        if isinstance(result.structured_content, dict):
            return result.structured_content
        return json.loads(text)
