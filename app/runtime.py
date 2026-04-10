from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys


@dataclass(slots=True)
class RuntimePaths:
    project_root: Path
    bundle_root: Path
    frontend_dist_dir: Path
    openapi_path: Path
    app_home: Path
    data_dir: Path
    cache_dir: Path
    logs_dir: Path
    config_dir: Path
    frozen: bool


def resolve_runtime_paths(
    *,
    project_root: Path | None = None,
    frozen: bool | None = None,
    env: dict[str, str] | None = None,
) -> RuntimePaths:
    env_map = env if env is not None else os.environ
    runtime_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    bundle_root = _resolve_bundle_root(project_root=project_root, frozen=runtime_frozen)
    app_home = _resolve_app_home(project_root=bundle_root, frozen=runtime_frozen, env=env_map)
    data_dir = app_home / "data" if runtime_frozen else app_home
    return RuntimePaths(
        project_root=bundle_root,
        bundle_root=bundle_root,
        frontend_dist_dir=bundle_root / "frontend" / "dist",
        openapi_path=bundle_root / "openapi.yaml",
        app_home=app_home,
        data_dir=data_dir,
        cache_dir=app_home / "cache",
        logs_dir=app_home / "logs",
        config_dir=app_home / "config",
        frozen=runtime_frozen,
    )


def _resolve_bundle_root(*, project_root: Path | None, frozen: bool) -> Path:
    if project_root is not None:
        return project_root.resolve()
    if frozen:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(str(meipass)).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _resolve_app_home(*, project_root: Path, frozen: bool, env: dict[str, str]) -> Path:
    override = env.get("MANAGED_AGENT_HOME")
    if override:
        return Path(override).resolve()
    if frozen:
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "Managed Agent").resolve()
        return (Path.home() / "AppData" / "Local" / "Managed Agent").resolve()
    return (project_root / ".data").resolve()
