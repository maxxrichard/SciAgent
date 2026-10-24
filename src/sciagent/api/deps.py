from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from sciagent.api.container import Container
from sciagent.core.errors import PolicyDenied
from sciagent.core.security import Principal


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_principal(
    container: ContainerDep, x_api_key: Annotated[str | None, Header()] = None
) -> Principal:
    return container.auth.authenticate(x_api_key)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_admin(principal: PrincipalDep) -> Principal:
    if not principal.is_admin:
        raise PolicyDenied("admin role required")
    return principal


AdminDep = Annotated[Principal, Depends(require_admin)]
