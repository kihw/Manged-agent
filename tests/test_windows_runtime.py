from __future__ import annotations

from pathlib import Path

from app.services.settings import resolve_settings
from app.runtime import resolve_runtime_paths


def test_resolve_runtime_paths_uses_checkout_paths_in_source_mode(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "app" / "templates").mkdir(parents=True)
    (repo_root / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")

    paths = resolve_runtime_paths(
        project_root=repo_root,
        frozen=False,
        env={},
    )

    assert paths.bundle_root == repo_root
    assert paths.templates_dir == repo_root / "app" / "templates"
    assert paths.openapi_path == repo_root / "openapi.yaml"
    assert paths.data_dir == (repo_root / ".data").resolve()


def test_resolve_runtime_paths_uses_local_appdata_when_frozen(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    local_app_data = tmp_path / "LocalAppData"
    (bundle_root / "app" / "templates").mkdir(parents=True)
    (bundle_root / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")

    paths = resolve_runtime_paths(
        project_root=bundle_root,
        frozen=True,
        env={"LOCALAPPDATA": str(local_app_data)},
    )

    assert paths.bundle_root == bundle_root
    assert paths.data_dir == (local_app_data / "Managed Agent" / "data").resolve()
    assert paths.logs_dir == (local_app_data / "Managed Agent" / "logs").resolve()
    assert paths.cache_dir == (local_app_data / "Managed Agent" / "cache").resolve()


def test_resolve_settings_defaults_to_sqlite_for_frozen_runtime(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    local_app_data = tmp_path / "LocalAppData"
    (bundle_root / "app" / "templates").mkdir(parents=True)
    (bundle_root / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    runtime_paths = resolve_runtime_paths(
        project_root=bundle_root,
        frozen=True,
        env={"LOCALAPPDATA": str(local_app_data)},
    )

    settings = resolve_settings(
        env={"DATABASE_URL": "postgresql://db.example/managed-agent"},
        runtime_paths=runtime_paths,
    )

    assert settings.storage_backend == "sqlite"
    assert settings.db_path == runtime_paths.data_dir / "managed-agent-v1.db"
    assert settings.database_url == "postgresql://db.example/managed-agent"


def test_resolve_settings_keeps_postgres_default_in_source_mode(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "app" / "templates").mkdir(parents=True)
    (repo_root / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    runtime_paths = resolve_runtime_paths(
        project_root=repo_root,
        frozen=False,
        env={},
    )

    settings = resolve_settings(
        env={"DATABASE_URL": "postgresql://db.example/managed-agent"},
        runtime_paths=runtime_paths,
    )

    assert settings.storage_backend == "postgres"
    assert settings.db_path == runtime_paths.data_dir / "managed-agent-v1.db"
