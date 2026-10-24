"""Build an MCP server exposing every registry tool that belongs to one domain.

Each tool's pydantic input model is flattened into the wrapper's signature so the
MCP ``inputSchema`` matches the registry schema field-for-field. Validation and
metrics then run through :meth:`ToolRegistry.call`, exactly as for local calls.
"""

from __future__ import annotations

import inspect
from typing import Annotated, Any, cast

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from sciagent import __version__
from sciagent.core.errors import SciAgentError
from sciagent.core.telemetry import REGISTRY
from sciagent.tools.registry import Tool, ToolRegistry, default_registry

SERVER_NAMES = ("imaging", "genomics", "clinical")


def _wrapper(registry: ToolRegistry, tool: Tool) -> Any:
    def call(**kwargs: Any) -> dict[str, Any]:
        try:
            return registry.call(tool.name, kwargs)
        except SciAgentError as exc:
            raise ToolError(f"{exc.code}: {exc.message} {exc.details}") from exc

    params = []
    for name, field in tool.input_model.model_fields.items():
        default = inspect.Parameter.empty if field.is_required() else field.default
        # Carry pydantic constraints (pattern, ge/le, lengths) into the MCP schema.
        annotation = cast(Any, Annotated)[
            (field.annotation, *field.metadata, Field(description=field.description))
        ]
        params.append(
            inspect.Parameter(
                name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation
            )
        )
    call.__signature__ = inspect.Signature(params, return_annotation=dict[str, Any])  # type: ignore[attr-defined]
    call.__annotations__ = {p.name: p.annotation for p in params} | {"return": dict[str, Any]}
    call.__name__ = tool.name
    call.__doc__ = tool.description
    return call


def build_server(name: str, registry: ToolRegistry | None = None) -> MCPServer:
    if name not in SERVER_NAMES:
        raise ValueError(f"unknown server '{name}', expected one of {SERVER_NAMES}")
    registry = registry or default_registry()
    server = MCPServer(
        name=f"sciagent-{name}",
        version=__version__,
        instructions=f"SciAgent {name} tools. All calls are policy-checked by the agent gateway.",
    )
    for tool in registry.by_server(name):
        server.add_tool(_wrapper(registry, tool), name=tool.name, description=tool.description)

    @server.custom_route("/metrics", methods=["GET"], include_in_schema=False)
    async def metrics(_: Request) -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok", "server": name})

    return server
