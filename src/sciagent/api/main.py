"""ASGI entry point: ``uvicorn sciagent.api.main:app``."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sciagent import __version__
from sciagent.api.container import Container, build_container
from sciagent.api.middleware import ObservabilityMiddleware
from sciagent.api.routers import agent, audit, datasets, health, tools
from sciagent.core.config import Settings, get_settings
from sciagent.core.errors import SciAgentError
from sciagent.core.logging import configure_logging, request_id_var


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not hasattr(app.state, "container"):
            app.state.container = build_container(settings)
        yield

    app = FastAPI(
        title="SciAgent API",
        version=__version__,
        description="Query, harmonise and analyse multimodal biological data with governed agents.",
        lifespan=lifespan,
    )
    if container is not None:
        app.state.container = container
    app.add_middleware(ObservabilityMiddleware, service="api")

    @app.exception_handler(SciAgentError)
    async def handle_domain_error(_: Request, exc: SciAgentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": json.loads(json.dumps(exc.details, default=str)),
                },
                "request_id": request_id_var.get(),
            },
        )

    for module in (health, datasets, tools, agent, audit):
        app.include_router(module.router)
    return app


app = create_app()
