"""Request-id propagation and Prometheus RED metrics."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from sciagent.core.logging import get_logger, request_id_var
from sciagent.core.telemetry import HTTP_LATENCY, HTTP_REQUESTS

log = get_logger("sciagent.access")


def _route_template(request: Request) -> str:
    for route in request.app.router.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return "unmatched"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, service: str = "api") -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.service = service

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        route = _route_template(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = rid
            return response
        finally:
            elapsed = time.perf_counter() - start
            HTTP_REQUESTS.labels(self.service, request.method, route, str(status)).inc()
            HTTP_LATENCY.labels(self.service, request.method, route).observe(elapsed)
            if route != "/metrics":
                log.info(
                    "request",
                    extra={
                        "fields": {
                            "method": request.method,
                            "route": route,
                            "status": status,
                            "ms": round(elapsed * 1000, 2),
                        }
                    },
                )
            request_id_var.reset(token)
