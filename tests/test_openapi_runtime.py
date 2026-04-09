from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.main import create_app


@pytest.fixture(autouse=True)
def force_local_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MANAGED_AGENT_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("MANAGED_AGENT_DB_PATH", str(tmp_path / "openapi-runtime.db"))


def test_runtime_openapi_matches_published_public_paths() -> None:
    published = yaml.safe_load(Path("openapi.yaml").read_text(encoding="utf-8"))
    runtime = create_app().openapi()

    published_paths = set(published["paths"].keys())
    runtime_paths = {path for path in runtime["paths"].keys() if path != "/healthz"}

    assert runtime_paths == published_paths


def test_runtime_openapi_keeps_instance_token_header_and_run_shapes() -> None:
    published = yaml.safe_load(Path("openapi.yaml").read_text(encoding="utf-8"))
    runtime = create_app().openapi()

    assert runtime["components"]["securitySchemes"] == published["components"]["securitySchemes"]
    assert runtime["paths"]["/v1/runs"]["post"]["responses"]["201"]["content"]["application/json"]["schema"] == published["paths"]["/v1/runs"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]
