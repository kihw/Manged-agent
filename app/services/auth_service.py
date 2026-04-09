from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class AuthStatus:
    mode: str
    user_id: str | None
    authenticated: bool


class AuthService(Protocol):
    async def get_status(self, user_id: str | None = None) -> AuthStatus:
        """Return current authentication mode and user context."""

    async def handle_oauth_callback(self, code: str, state: str) -> AuthStatus:
        """Exchange OAuth callback data for user session information."""
