"""Exceptions shared by the services and rendered by the API as {"detail": "..."}."""
from __future__ import annotations


class WorkflowError(Exception):
    """Raised for an illegal transition, a failed guard or an unauthorised actor. Rendered as HTTP 400/403."""

    def __init__(self, message, status: int = 400):
        super().__init__(message)
        self.status = status


class AuthError(Exception):
    """Invalid / missing credentials. Rendered as HTTP 401."""

    def __init__(self, message: str = "Authentication credentials were not provided."):
        super().__init__(message)
        self.status = 401
