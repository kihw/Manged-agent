from typing import Protocol

from app.models import AuthContext


class AuthService(Protocol):
    async def get_status(self, user_id: str | None = None) -> AuthContext:
        """Return current authentication mode and user context."""

    async def handle_oauth_callback(self, code: str, state: str) -> AuthContext:
        """Exchange OAuth callback data for user session information."""
