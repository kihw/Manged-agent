from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import secrets

from app.runtime import RuntimePaths, resolve_runtime_paths


@dataclass(slots=True)
class AppSettings:
    storage_backend: str = "sqlite"
    db_path: Path = field(default_factory=lambda: Path(".data/managed-agent-v1.db").resolve())
    database_url: str | None = None
    runtime_paths: RuntimePaths = field(default_factory=resolve_runtime_paths)
    admin_secret: str | None = None
    enforce_admin_auth: bool = False


def resolve_settings(
    *,
    env: dict[str, str] | None = None,
    runtime_paths: RuntimePaths | None = None,
) -> AppSettings:
    env_map = env if env is not None else os.environ
    paths = runtime_paths or resolve_runtime_paths(env=env_map)
    database_url = env_map.get("DATABASE_URL")
    storage_backend = env_map.get("MANAGED_AGENT_STORAGE_BACKEND")
    if storage_backend is None:
        storage_backend = "sqlite" if paths.frozen or not database_url else "postgres"
    return AppSettings(
        storage_backend=storage_backend,
        db_path=Path(env_map.get("MANAGED_AGENT_DB_PATH", str(paths.data_dir / "managed-agent-v1.db"))).resolve(),
        database_url=database_url,
        runtime_paths=paths,
        admin_secret=env_map.get("MANAGED_AGENT_ADMIN_SECRET") or None,
        enforce_admin_auth=(env_map.get("MANAGED_AGENT_ENFORCE_ADMIN_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}),
    )


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"
