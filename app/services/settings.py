from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import secrets


@dataclass(slots=True)
class AppSettings:
    storage_backend: str = "sqlite"
    db_path: Path = field(default_factory=lambda: Path(".data/managed-agent-v1.db").resolve())
    database_url: str | None = None


def resolve_settings() -> AppSettings:
    database_url = os.getenv("DATABASE_URL")
    return AppSettings(
        storage_backend=os.getenv("MANAGED_AGENT_STORAGE_BACKEND", "postgres" if database_url else "sqlite"),
        db_path=Path(os.getenv("MANAGED_AGENT_DB_PATH", ".data/managed-agent-v1.db")).resolve(),
        database_url=database_url,
    )


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"
