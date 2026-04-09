from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from codex_adapter.client import AdapterOfflineError, CodexPlatformAdapter


@pytest.fixture
def platform_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MANAGED_AGENT_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("MANAGED_AGENT_DB_PATH", str(tmp_path / "adapter-platform.db"))
    return TestClient(create_app())


def publish_orchestration(client: TestClient) -> None:
    response = client.post(
        "/v1/orchestrations",
        json={
            "orchestration_id": "orc_sync_repo",
            "name": "Sync repository",
            "version": "1.0.0",
            "status": "published",
            "entrypoint": "codex://orchestrations/sync-repo",
            "required_tools": ["shell", "http"],
            "required_skills": ["planning"],
            "policy_profile": "default",
            "compatibility": ["cli"],
            "published_at": "2026-04-09T18:00:00Z",
        },
    )
    assert response.status_code == 201


def test_adapter_registers_syncs_runs_and_queues_outbox(platform_client: TestClient, tmp_path: Path) -> None:
    publish_orchestration(platform_client)
    adapter = CodexPlatformAdapter(
        client=platform_client,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )

    instance = adapter.register_instance()
    sync = adapter.sync_orchestrations()
    start = adapter.start_run(
        orchestration_id="orc_sync_repo",
        title="Synchroniser les examples OpenAPI",
        goal="Rendre la nouvelle API visible dans le dashboard.",
        trigger="manual",
    )

    adapter.emit_events(
        run_id=start["run_id"],
        task_id=start["task_id"],
        events=[
            {
                "event_id": "evt_1111aaaa",
                "run_id": start["run_id"],
                "task_id": start["task_id"],
                "source": "codex",
                "type": "run.started",
                "timestamp": "2026-04-09T18:00:00Z",
                "payload": {"task_title": "Synchroniser les examples OpenAPI"},
            }
        ],
    )

    assert instance["instance_id"].startswith("inst_")
    assert sync["orchestrations"][0]["orchestration_id"] == "orc_sync_repo"
    assert (tmp_path / ".data" / "codex-adapter" / "instance.json").exists()
    assert (tmp_path / ".data" / "codex-adapter" / "orchestrations-cache.json").exists()
    assert (tmp_path / ".data" / "codex-adapter" / "outbox.jsonl").exists() is False


def test_adapter_uses_cache_but_refuses_start_run_offline(platform_client: TestClient, tmp_path: Path) -> None:
    publish_orchestration(platform_client)
    adapter = CodexPlatformAdapter(
        client=platform_client,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )
    adapter.register_instance()
    adapter.sync_orchestrations()

    offline_adapter = CodexPlatformAdapter(
        client=None,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )

    cached = offline_adapter.load_cached_orchestrations()
    assert cached[0]["orchestration_id"] == "orc_sync_repo"

    with pytest.raises(AdapterOfflineError):
        offline_adapter.start_run(
            orchestration_id="orc_sync_repo",
            title="Offline attempt",
            goal="Should fail without platform.",
            trigger="manual",
        )


def test_adapter_blocks_sensitive_action_when_platform_is_offline(platform_client: TestClient, tmp_path: Path) -> None:
    publish_orchestration(platform_client)
    online_adapter = CodexPlatformAdapter(
        client=platform_client,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )
    online_adapter.register_instance()
    start = online_adapter.start_run(
        orchestration_id="orc_sync_repo",
        title="Need network",
        goal="Trigger approval flow.",
        trigger="manual",
    )

    offline_adapter = CodexPlatformAdapter(
        client=None,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )

    with pytest.raises(AdapterOfflineError):
        offline_adapter.preauthorize(
            run_id=start["run_id"],
            task_id=start["task_id"],
            action_type="outbound_network",
            target="https://api.example.dev/packages",
            tool_name="http",
            metadata={"method": "GET"},
        )


class ErroringClient:
    def __init__(self, *, get_status: int = 200, post_status: int = 200) -> None:
        self.get_status = get_status
        self.post_status = post_status

    def get(self, url: str, **_: object) -> httpx.Response:
        return httpx.Response(
            self.get_status,
            json={"code": "upstream_error", "message": "GET failed"},
            request=httpx.Request("GET", f"http://testserver{url}"),
        )

    def post(self, url: str, **_: object) -> httpx.Response:
        return httpx.Response(
            self.post_status,
            json={"code": "upstream_error", "message": "POST failed"},
            request=httpx.Request("POST", f"http://testserver{url}"),
        )


def test_adapter_raises_http_error_for_missing_orchestration(platform_client: TestClient, tmp_path: Path) -> None:
    adapter = CodexPlatformAdapter(
        client=platform_client,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )
    adapter.register_instance()

    with pytest.raises(httpx.HTTPStatusError):
        adapter.start_run(
            orchestration_id="orc_missing",
            title="Missing orchestration",
            goal="Should raise.",
            trigger="manual",
        )


def test_adapter_does_not_write_caches_when_register_or_sync_fails(tmp_path: Path) -> None:
    cache_dir = tmp_path / ".data" / "codex-adapter"

    register_adapter = CodexPlatformAdapter(
        client=ErroringClient(post_status=503),
        cache_dir=cache_dir,
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell"],
        machine_id="machine_devbox",
    )
    with pytest.raises(httpx.HTTPStatusError):
        register_adapter.register_instance()
    assert (cache_dir / "instance.json").exists() is False

    instance_payload = {
        "instance_id": "inst_1234abcd",
        "instance_token": "itok_1234abcd",
        "registered_at": "2026-04-09T18:00:00Z",
    }
    (cache_dir / "instance.json").write_text(json.dumps(instance_payload), encoding="utf-8")

    sync_adapter = CodexPlatformAdapter(
        client=ErroringClient(get_status=503),
        cache_dir=cache_dir,
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell"],
        machine_id="machine_devbox",
    )
    with pytest.raises(httpx.HTTPStatusError):
        sync_adapter.sync_orchestrations()
    assert (cache_dir / "orchestrations-cache.json").exists() is False


def test_adapter_keeps_outbox_when_flush_fails(platform_client: TestClient, tmp_path: Path) -> None:
    publish_orchestration(platform_client)
    online_adapter = CodexPlatformAdapter(
        client=platform_client,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )
    online_adapter.register_instance()
    start = online_adapter.start_run(
        orchestration_id="orc_sync_repo",
        title="Queue then flush",
        goal="Keep outbox on server failure.",
        trigger="manual",
    )

    offline_adapter = CodexPlatformAdapter(
        client=None,
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )
    with pytest.raises(AdapterOfflineError):
        offline_adapter.emit_events(
            run_id=start["run_id"],
            task_id=start["task_id"],
            events=[
                {
                    "event_id": "evt_flushfail01",
                    "run_id": start["run_id"],
                    "task_id": start["task_id"],
                    "source": "codex",
                    "type": "heartbeat",
                    "timestamp": "2026-04-09T18:01:00Z",
                    "payload": {},
                }
            ],
        )

    failing_adapter = CodexPlatformAdapter(
        client=ErroringClient(post_status=503),
        cache_dir=tmp_path / ".data" / "codex-adapter",
        client_kind="cli",
        workspace_path="D:/Code/Manged-agent",
        capabilities=["shell", "http"],
        machine_id="machine_devbox",
    )
    with pytest.raises(httpx.HTTPStatusError):
        failing_adapter.flush_outbox()
    assert failing_adapter.outbox_file.exists()
    assert "evt_flushfail01" in failing_adapter.outbox_file.read_text(encoding="utf-8")
