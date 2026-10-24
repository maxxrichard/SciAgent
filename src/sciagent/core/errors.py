"""Domain errors mapped to HTTP status codes by the API layer."""

from __future__ import annotations


class SciAgentError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(SciAgentError):
    status_code = 404
    code = "not_found"


class ValidationFailed(SciAgentError):
    status_code = 422
    code = "validation_failed"


class AuthenticationError(SciAgentError):
    status_code = 401
    code = "unauthenticated"


class PolicyDenied(SciAgentError):
    status_code = 403
    code = "policy_denied"


class GuardrailViolation(SciAgentError):
    status_code = 400
    code = "guardrail_violation"


class ToolExecutionError(SciAgentError):
    status_code = 502
    code = "tool_error"
