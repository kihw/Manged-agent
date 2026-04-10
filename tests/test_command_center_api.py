from __future__ import annotations

from importlib import reload
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import app.main as app_main


def build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MANAGED_AGENT_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("MANAGED_AGENT_DB_PATH", str(tmp_path / "managed-agent-v1.db"))
    monkeypatch.setenv("MANAGED_AGENT_HOME", str(tmp_path / "managed-agent-home"))
    reload(app_main)
    return TestClient(app_main.create_app())


def publish_orchestration(client: TestClient, orchestration_id: str, *, name: str) -> None:
    response = client.post(
        "/v1/orchestrations",
        json={
            "orchestration_id": orchestration_id,
            "name": name,
            "version": "1.0.0",
            "status": "published",
            "entrypoint": f"codex://orchestrations/{orchestration_id}",
            "required_tools": ["shell"],
            "required_skills": [],
            "policy_profile": "default",
            "compatibility": ["cli", "windows_app"],
            "published_at": "2026-04-09T18:00:00Z",
        },
    )
    assert response.status_code == 201


def register_cli_instance(client: TestClient, workspace_path: str, machine_id: str) -> dict[str, str]:
    response = client.post(
        "/v1/instances/register",
        json={
            "client_kind": "cli",
            "workspace_path": workspace_path,
            "capabilities": ["shell"],
            "machine_id": machine_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_command_center_exposes_projects_queues_and_urgent_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        publish_orchestration(client, "orc_atlas_sync", name="Atlas Sync")
        cli_instance = register_cli_instance(client, "D:/Projects/Atlas", "machine_atlas")
        headers = {"X-Instance-Token": cli_instance["instance_token"]}

        running = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_atlas_sync",
                "instance_id": cli_instance["instance_id"],
                "title": "Atlas running",
                "goal": "Keep Atlas healthy",
                "workspace_path": "D:/Projects/Atlas",
                "trigger": "manual",
            },
        ).json()
        client.post(
            f"/v1/runs/{running['run_id']}/events:batch",
            headers=headers,
            json={
                "events": [
                    {
                        "event_id": "evt_running001",
                        "run_id": running["run_id"],
                        "task_id": running["task_id"],
                        "source": "codex",
                        "type": "run.started",
                        "timestamp": "2026-04-09T18:00:00Z",
                        "payload": {"task_title": "Atlas running", "step_name": "sync"},
                    }
                ]
            },
        )

        blocked = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_atlas_sync",
                "instance_id": cli_instance["instance_id"],
                "title": "Atlas blocked",
                "goal": "Needs approval",
                "workspace_path": "D:/Projects/Atlas",
                "trigger": "manual",
            },
        ).json()
        decision = client.post(
            "/v1/policy/preauthorize",
            headers=headers,
            json={
                "run_id": blocked["run_id"],
                "task_id": blocked["task_id"],
                "action_type": "outbound_network",
                "target": "https://example.dev/artifacts",
                "workspace_path": "D:/Projects/Atlas",
                "tool_name": "http",
                "metadata": {"method": "GET"},
            },
        ).json()

        failed = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_atlas_sync",
                "instance_id": cli_instance["instance_id"],
                "title": "Beta failure",
                "goal": "Investigate failure",
                "workspace_path": "D:/Projects/Beta",
                "trigger": "manual",
            },
        ).json()
        client.post(
            f"/v1/runs/{failed['run_id']}/events:batch",
            headers=headers,
            json={
                "events": [
                    {
                        "event_id": "evt_failed001",
                        "run_id": failed["run_id"],
                        "task_id": failed["task_id"],
                        "source": "codex",
                        "type": "run.started",
                        "timestamp": "2026-04-09T18:10:00Z",
                        "payload": {"task_title": "Beta failure", "step_name": "collect"},
                    },
                    {
                        "event_id": "evt_failed002",
                        "run_id": failed["run_id"],
                        "task_id": failed["task_id"],
                        "source": "codex",
                        "type": "error.raised",
                        "timestamp": "2026-04-09T18:11:00Z",
                        "payload": {"task_title": "Beta failure", "error_category": "network_timeout", "message": "Timed out"},
                    },
                ]
            },
        )
        client.post(
            f"/v1/runs/{failed['run_id']}/complete",
            headers=headers,
            json={
                "status": "failed",
                "summary": "Beta failed",
                "ended_at": "2026-04-09T18:12:00Z",
            },
        )

        response = client.get("/v1/dashboard/command-center")

    assert response.status_code == 200
    payload = response.json()
    assert payload["executive"]["active_runs"] == 1
    assert payload["executive"]["blocked_runs"] == 1
    assert payload["executive"]["pending_approvals"] == 1
    assert payload["runtime"]["local_instance_id"].startswith("inst_")
    assert {project["display_name"] for project in payload["projects"]} >= {"Atlas", "Beta"}
    assert payload["queues"]["in_progress"][0]["title"] == "Atlas running"
    assert payload["queues"]["blocked"][0]["run_id"] == blocked["run_id"]
    assert payload["urgent"]["approvals"][0]["decision_id"] == decision["decision_id"]
    assert payload["urgent"]["errors"][0]["category"] == "network_timeout"
    assert payload["available_orchestrations"][0]["orchestration_id"] == "orc_atlas_sync"


def test_dashboard_launch_uses_local_desktop_instance_and_persists_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        publish_orchestration(client, "orc_launch_ui", name="Launch UI")
        response = client.post(
            "/v1/dashboard/runs/launch",
            json={
                "orchestration_id": "orc_launch_ui",
                "title": "Launched from UI",
                "goal": "Run from the command center",
                "workspace_path": "D:/Projects/Launch",
                "trigger": "manual-ui",
            },
        )
        command_center = client.get("/v1/dashboard/command-center")
        config_path = client.app.state.runtime_paths.config_dir / "desktop-instance.json"

    assert response.status_code == 201
    run_payload = response.json()
    assert run_payload["run_id"].startswith("run_")
    assert config_path.exists()
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["instance_id"] == command_center.json()["runtime"]["local_instance_id"]
    run_detail = command_center.json()["queues"]["in_progress"][0]
    assert run_detail["title"] == "Launched from UI"
    assert run_detail["workspace_path"] == "D:/Projects/Launch"


def test_dashboard_relaunch_reuses_existing_run_defaults_and_allows_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        publish_orchestration(client, "orc_relaunch_ui", name="Relaunch UI")
        first = client.post(
            "/v1/dashboard/runs/launch",
            json={
                "orchestration_id": "orc_relaunch_ui",
                "title": "Initial UI task",
                "goal": "First run",
                "workspace_path": "D:/Projects/Relaunch",
                "trigger": "manual-ui",
            },
        ).json()

        response = client.post(
            f"/v1/dashboard/runs/{first['run_id']}/relaunch",
            json={
                "title": "Relaunched UI task",
                "trigger": "rerun-ui",
            },
        )
        dashboard_runs = client.get("/v1/dashboard/runs")

    assert response.status_code == 201
    relaunch = response.json()
    assert relaunch["run_id"] != first["run_id"]
    run_ids = {run["run_id"] for run in dashboard_runs.json()}
    assert first["run_id"] in run_ids
    assert relaunch["run_id"] in run_ids

    relaunched_detail = next(run for run in dashboard_runs.json() if run["run_id"] == relaunch["run_id"])
    assert relaunched_detail["workspace_path"] == "D:/Projects/Relaunch"
