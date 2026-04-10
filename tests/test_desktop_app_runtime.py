from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime import resolve_runtime_paths
from app.services.settings import resolve_settings


def write_bundle_fixture(bundle_root: Path) -> None:
    frontend_dist = bundle_root / "frontend" / "dist"
    assets = frontend_dist / "assets"
    assets.mkdir(parents=True)
    (bundle_root / "openapi.yaml").write_text(
        "openapi: 3.1.0\npaths:\n  /v1/dashboard/overview: {}\ncomponents:\n  securitySchemes: {}\n",
        encoding="utf-8",
    )
    (frontend_dist / "index.html").write_text(
        """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script type="module" src="/dashboard/assets/app.js"></script>
  </head>
  <body>
    <div id="root">Bundled command center shell</div>
  </body>
</html>
""",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('Bundled frontend asset');", encoding="utf-8")


def test_create_app_loads_openapi_and_frontend_shell_from_runtime_bundle(tmp_path: Path) -> None:
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
        deep_link = client.get("/dashboard/runs")
        asset = client.get("/dashboard/assets/app.js")

    assert openapi.status_code == 200
    assert "openapi: 3.1.0" in openapi.text
    assert dashboard.status_code == 200
    assert "Bundled command center shell" in dashboard.text
    assert deep_link.status_code == 200
    assert "Bundled command center shell" in deep_link.text
    assert asset.status_code == 200
    assert "Bundled frontend asset" in asset.text


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


def test_enforced_admin_auth_accepts_query_secret_then_cookie_for_spa_routes(tmp_path: Path) -> None:
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
    assert "Bundled command center shell" in bootstrap.text
    assert "managed_agent_admin=" in bootstrap.headers["set-cookie"]
    assert follow_up.status_code == 200
    assert "Bundled command center shell" in follow_up.text
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
