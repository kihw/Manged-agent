from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.runtime import resolve_runtime_paths
from app.services.settings import resolve_settings


def write_bundle_fixture(bundle_root: Path) -> None:
    templates = bundle_root / "app" / "templates"
    templates.mkdir(parents=True)
    (bundle_root / "openapi.yaml").write_text(
        "openapi: 3.1.0\npaths:\n  /v1/dashboard/overview: {}\ncomponents:\n  securitySchemes: {}\n",
        encoding="utf-8",
    )
    (templates / "overview.html").write_text("Bundled overview", encoding="utf-8")
    (templates / "runs.html").write_text("Bundled runs", encoding="utf-8")
    (templates / "instances.html").write_text("Bundled instances", encoding="utf-8")
    (templates / "orchestrations.html").write_text("Bundled orchestrations", encoding="utf-8")
    (templates / "run_detail.html").write_text("Bundled run detail", encoding="utf-8")
    (templates / "workflows.html").write_text("Bundled workflows", encoding="utf-8")
    (templates / "workflow_detail.html").write_text("Bundled workflow detail", encoding="utf-8")
    (templates / "errors.html").write_text("Bundled errors", encoding="utf-8")
    (templates / "error_detail.html").write_text("Bundled error detail", encoding="utf-8")


def test_create_app_loads_openapi_and_templates_from_runtime_bundle(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    write_bundle_fixture(bundle_root)
    runtime_paths = resolve_runtime_paths(
        project_root=bundle_root,
        frozen=True,
        env={"LOCALAPPDATA": str(tmp_path / "LocalAppData")},
    )
    settings = resolve_settings(
        env={"MANAGED_AGENT_STORAGE_BACKEND": "sqlite"},
        runtime_paths=runtime_paths,
    )

    with TestClient(create_app(settings=settings, runtime_paths=runtime_paths)) as client:
        openapi = client.get("/openapi.yaml")
        dashboard = client.get("/dashboard")

    assert openapi.status_code == 200
    assert "openapi: 3.1.0" in openapi.text
    assert dashboard.status_code == 200
    assert "Bundled overview" in dashboard.text


def test_enforced_admin_auth_rejects_dashboard_without_secret(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    write_bundle_fixture(bundle_root)
    runtime_paths = resolve_runtime_paths(
        project_root=bundle_root,
        frozen=True,
        env={"LOCALAPPDATA": str(tmp_path / "LocalAppData")},
    )
    settings = resolve_settings(
        env={
            "MANAGED_AGENT_STORAGE_BACKEND": "sqlite",
            "MANAGED_AGENT_ENFORCE_ADMIN_AUTH": "true",
            "MANAGED_AGENT_ADMIN_SECRET": "top-secret",
        },
        runtime_paths=runtime_paths,
    )

    with TestClient(create_app(settings=settings, runtime_paths=runtime_paths)) as client:
        healthz = client.get("/healthz")
        dashboard = client.get("/dashboard")
        api = client.get("/v1/dashboard/overview")

    assert healthz.status_code == 200
    assert dashboard.status_code == 401
    assert dashboard.json()["code"] == "admin_auth_required"
    assert api.status_code == 401


def test_enforced_admin_auth_accepts_query_secret_then_cookie(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    write_bundle_fixture(bundle_root)
    runtime_paths = resolve_runtime_paths(
        project_root=bundle_root,
        frozen=True,
        env={"LOCALAPPDATA": str(tmp_path / "LocalAppData")},
    )
    settings = resolve_settings(
        env={
            "MANAGED_AGENT_STORAGE_BACKEND": "sqlite",
            "MANAGED_AGENT_ENFORCE_ADMIN_AUTH": "true",
            "MANAGED_AGENT_ADMIN_SECRET": "top-secret",
        },
        runtime_paths=runtime_paths,
    )

    with TestClient(create_app(settings=settings, runtime_paths=runtime_paths)) as client:
        bootstrap = client.get("/dashboard", params={"admin_secret": "top-secret"})
        follow_up = client.get("/dashboard/runs")
        api = client.get("/v1/dashboard/overview", headers={"X-Admin-Secret": "top-secret"})

    assert bootstrap.status_code == 200
    assert "managed_agent_admin=" in bootstrap.headers["set-cookie"]
    assert follow_up.status_code == 200
    assert api.status_code == 200


def test_frozen_runtime_persists_sqlite_in_local_appdata(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    local_app_data = tmp_path / "LocalAppData"
    write_bundle_fixture(bundle_root)
    runtime_paths = resolve_runtime_paths(
        project_root=bundle_root,
        frozen=True,
        env={"LOCALAPPDATA": str(local_app_data)},
    )
    settings = resolve_settings(
        env={"MANAGED_AGENT_STORAGE_BACKEND": "sqlite"},
        runtime_paths=runtime_paths,
    )

    with TestClient(create_app(settings=settings, runtime_paths=runtime_paths)) as client:
        response = client.get("/v1/dashboard/overview")

    assert response.status_code == 200
    assert settings.db_path == local_app_data / "Managed Agent" / "data" / "managed-agent-v1.db"
    assert settings.db_path.exists()
