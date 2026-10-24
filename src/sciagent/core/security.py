"""API-key authentication and principal model.

Keys are configured via ``SCIAGENT_API_KEYS`` in production from a Kubernetes
Secret. Only SHA-256 digests are kept in memory after start-up.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Literal

from sciagent.core.errors import AuthenticationError, ValidationFailed

Role = Literal["researcher", "analyst", "admin"]
_ROLES: tuple[str, ...] = ("researcher", "analyst", "admin")


@dataclass(frozen=True)
class Principal:
    user: str
    role: Role
    groups: frozenset[str] = field(default_factory=frozenset)

    def in_group(self, group: str) -> bool:
        return "*" in self.groups or group in self.groups

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyAuthenticator:
    def __init__(self, spec: str) -> None:
        self._principals: dict[str, Principal] = {}
        for raw in filter(None, (s.strip() for s in spec.split(","))):
            parts = raw.split(":")
            if len(parts) != 4 or parts[2] not in _ROLES:
                raise ValidationFailed("malformed api key entry", entry=parts[1:2])
            key, user, role, groups = parts
            self._principals[_digest(key)] = Principal(
                user=user,
                role=role,  # type: ignore[arg-type]
                groups=frozenset(g for g in groups.split("|") if g),
            )

    def authenticate(self, key: str | None) -> Principal:
        if not key:
            raise AuthenticationError("missing API key")
        digest = _digest(key)
        for known, principal in self._principals.items():
            if hmac.compare_digest(known, digest):
                return principal
        raise AuthenticationError("invalid API key")
