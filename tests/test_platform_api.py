from __future__ import annotations

from importlib import reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as app_main
from app.runtime import resolve_runtime_paths


def seed_frontend_bundle(runtime_root: Path) -> Path:
    frontend_dist = runtime_root / "frontend" / "dist"
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    frontend_dist.joinpath("index.html").write_text(
        """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script type="module" src="/dashboard/assets/app.js"></script>
  </head>
  <body>
    <div id="root">Managed Agent Command Center</div>
  </body>
</html>
""",
        encoding="utf-8",
    )
    assets_dir.joinpath("app.js").write_text("console.log('command-center');", encoding="utf-8")
    runtime_root.joinpath("openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    return runtime_root


def build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MANAGED_AGENT_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("MANAGED_AGENT_DB_PATH", str(tmp_path / "managed-agent-v1.db"))
    reload(app_main)
    runtime_paths = resolve_runtime_paths(project_root=seed_frontend_bundle(tmp_path / "runtime"), frozen=False, env={})
    return TestClient(app_main.create_app(runtime_paths=runtime_paths))


def test_platform_supports_publish_sync_run_policy_and_dashboard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        publish_response = client.post(
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
                "compatibility": ["cli", "windows_app"],
                "published_at": "2026-04-09T18:00:00Z",
            },
        )
        assert publish_response.status_code == 201

        register_response = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["shell", "http"],
                "machine_id": "machine_devbox",
            },
        )
        assert register_response.status_code == 201
        instance = register_response.json()
        headers = {"X-Instance-Token": instance["instance_token"]}

        sync_response = client.get("/v1/orchestrations/sync", headers=headers)
        assert sync_response.status_code == 200
        assert sync_response.json()["orchestrations"][0]["orchestration_id"] == "orc_sync_repo"

        run_response = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_sync_repo",
                "instance_id": instance["instance_id"],
                "title": "Synchroniser les examples OpenAPI",
                "goal": "Rendre la nouvelle API visible dans le dashboard.",
                "workspace_path": "D:/Code/Manged-agent",
                "trigger": "manual",
            },
        )
        assert run_response.status_code == 201
        run_payload = run_response.json()
        run_id = run_payload["run_id"]
        task_id = run_payload["task_id"]

        batch_response = client.post(
            f"/v1/runs/{run_id}/events:batch",
            headers=headers,
            json={
                "events": [
                    {
                        "event_id": "evt_1111aaaa",
                        "run_id": run_id,
                        "task_id": task_id,
                        "source": "codex",
                        "type": "run.started",
                        "timestamp": "2026-04-09T18:00:00Z",
                        "payload": {"task_title": "Synchroniser les examples OpenAPI"},
                    },
                    {
                        "event_id": "evt_2222bbbb",
                        "run_id": run_id,
                        "task_id": task_id,
                        "source": "codex",
                        "type": "tool.called",
                        "timestamp": "2026-04-09T18:00:03Z",
                        "payload": {
                            "task_title": "Synchroniser les examples OpenAPI",
                            "tool_name": "shell",
                            "input_summary": "python scripts/validate_openapi_spec.py",
                        },
                    },
                    {
                        "event_id": "evt_3333cccc",
                        "run_id": run_id,
                        "task_id": task_id,
                        "source": "codex",
                        "type": "tool.completed",
                        "timestamp": "2026-04-09T18:00:05Z",
                        "payload": {
                            "task_title": "Synchroniser les examples OpenAPI",
                            "tool_name": "shell",
                            "output_summary": "spec valid",
                        },
                    },
                ]
            },
        )
        assert batch_response.status_code == 202
        assert batch_response.json() == {"accepted": 3}

        decision_response = client.post(
            "/v1/policy/preauthorize",
            headers=headers,
            json={
                "run_id": run_id,
                "task_id": task_id,
                "action_type": "outbound_network",
                "target": "https://api.example.dev/packages",
                "workspace_path": "D:/Code/Manged-agent",
                "tool_name": "http",
                "metadata": {"method": "GET"},
            },
        )
        assert decision_response.status_code == 200
        decision = decision_response.json()
        assert decision["decision"] == "require_approval"
        assert decision["status"] == "pending"

        fetched_decision = client.get(f"/v1/policy-decisions/{decision['decision_id']}", headers=headers)
        assert fetched_decision.status_code == 200
        assert fetched_decision.json()["decision_id"] == decision["decision_id"]

        resolve_response = client.post(
            f"/v1/policy-decisions/{decision['decision_id']}/resolve",
            json={"resolution": "approved", "resolved_by": "dashboard-user", "comment": "OK"},
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["status"] == "approved"

        complete_response = client.post(
            f"/v1/runs/{run_id}/complete",
            headers=headers,
            json={
                "status": "completed",
                "summary": "Run completed successfully.",
                "ended_at": "2026-04-09T18:10:00Z",
            },
        )
        assert complete_response.status_code == 200

        run_detail = client.get(f"/v1/runs/{run_id}", headers=headers)
        assert run_detail.status_code == 200
        assert run_detail.json()["run"]["status"] == "completed"
        assert run_detail.json()["task"]["title"] == "Synchroniser les examples OpenAPI"
        assert run_detail.json()["tool_executions"][0]["tool_name"] == "shell"
        assert run_detail.json()["policy_decisions"][0]["status"] == "approved"
        assert run_detail.json()["fingerprint"]["occurrence_count"] == 1

        task_detail = client.get(f"/v1/tasks/{task_id}", headers=headers)
        assert task_detail.status_code == 200
        assert task_detail.json()["task_id"] == task_id
        assert task_detail.json()["status"] == "completed"

        overview = client.get("/v1/dashboard/overview")
        assert overview.status_code == 200
        assert overview.json()["orchestration_count"] == 1
        assert overview.json()["active_instance_count"] >= 1
        assert overview.json()["blocked_run_count"] == 0

        runs = client.get("/v1/dashboard/runs")
        assert runs.status_code == 200
        assert runs.json()[0]["run_id"] == run_id

        dashboard_detail = client.get(f"/v1/dashboard/runs/{run_id}")
        assert dashboard_detail.status_code == 200
        dashboard_payload = dashboard_detail.json()
        assert dashboard_payload["task"]["title"] == "Synchroniser les examples OpenAPI"
        assert dashboard_payload["tool_executions"][0]["output_summary"] == "spec valid"


def test_platform_rejects_calls_with_unknown_instance_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        response = client.get("/v1/orchestrations/sync", headers={"X-Instance-Token": "itok_missing"})

        assert response.status_code == 401
        assert response.json()["code"] == "invalid_instance_token"


def test_dashboard_spa_shell_exposes_deep_links_and_json_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        client.post(
            "/v1/orchestrations",
            json={
                "orchestration_id": "orc_dashboard",
                "name": "Dashboard orchestration",
                "version": "1.0.0",
                "status": "published",
                "entrypoint": "codex://orchestrations/dashboard",
                "required_tools": ["shell"],
                "required_skills": [],
                "policy_profile": "default",
                "compatibility": ["cli"],
                "published_at": "2026-04-09T18:00:00Z",
            },
        )
        register_response = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["shell"],
                "machine_id": "machine_dashboard",
            },
        )
        headers = {"X-Instance-Token": register_response.json()["instance_token"]}
        run_response = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_dashboard",
                "instance_id": register_response.json()["instance_id"],
                "title": "Dashboard run",
                "goal": "Check dashboard pages",
                "workspace_path": "D:/Code/Manged-agent",
                "trigger": "manual",
            },
        )
        run_id = run_response.json()["run_id"]

        overview = client.get("/dashboard")
        runs = client.get("/dashboard/runs")
        instances = client.get("/dashboard/instances")
        orchestrations = client.get("/dashboard/orchestrations")
        detail = client.get(f"/dashboard/runs/{run_id}")

        assert overview.status_code == 200
        assert runs.status_code == 200
        assert instances.status_code == 200
        assert orchestrations.status_code == 200
        assert detail.status_code == 200
        assert "Managed Agent Command Center" in overview.text
        assert "Managed Agent Command Center" in runs.text
        assert "Managed Agent Command Center" in instances.text
        assert "Managed Agent Command Center" in orchestrations.text
        assert "Managed Agent Command Center" in detail.text

        orchestrations_json = client.get("/v1/dashboard/orchestrations")
        instances_json = client.get("/v1/dashboard/instances")
        detail_json = client.get(f"/v1/dashboard/runs/{run_id}")

        assert orchestrations_json.status_code == 200
        assert instances_json.status_code == 200
        assert detail_json.status_code == 200
        assert orchestrations_json.json()[0]["name"] == "Dashboard orchestration"
        assert any(instance["machine_id"] == "machine_dashboard" for instance in instances_json.json())
        assert detail_json.json()["task"]["title"] == "Dashboard run"


def test_dashboard_form_can_resolve_pending_policy_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        client.post(
            "/v1/orchestrations",
            json={
                "orchestration_id": "orc_policy_form",
                "name": "Policy form orchestration",
                "version": "1.0.0",
                "status": "published",
                "entrypoint": "codex://orchestrations/policy-form",
                "required_tools": ["http"],
                "required_skills": [],
                "policy_profile": "default",
                "compatibility": ["cli"],
                "published_at": "2026-04-09T18:00:00Z",
            },
        )
        register_response = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["http"],
                "machine_id": "machine_form",
            },
        )
        headers = {"X-Instance-Token": register_response.json()["instance_token"]}
        run_response = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_policy_form",
                "instance_id": register_response.json()["instance_id"],
                "title": "Need approval",
                "goal": "Resolve approval from dashboard form",
                "workspace_path": "D:/Code/Manged-agent",
                "trigger": "manual",
            },
        )
        run_id = run_response.json()["run_id"]
        task_id = run_response.json()["task_id"]
        decision_response = client.post(
            "/v1/policy/preauthorize",
            headers=headers,
            json={
                "run_id": run_id,
                "task_id": task_id,
                "action_type": "outbound_network",
                "target": "https://api.example.dev/packages",
                "workspace_path": "D:/Code/Manged-agent",
                "tool_name": "http",
                "metadata": {"method": "GET"},
            },
        )
        decision_id = decision_response.json()["decision_id"]

        form_response = client.post(
            f"/v1/policy-decisions/{decision_id}/resolve",
            data={"resolution": "approved", "resolved_by": "dashboard"},
            follow_redirects=False,
        )

        assert form_response.status_code == 303
        assert form_response.headers["location"] == f"/dashboard/runs/{run_id}"
        resolved = client.get(f"/v1/policy-decisions/{decision_id}", headers=headers)
        assert resolved.json()["status"] == "approved"


def test_dashboard_overview_exposes_top_workflows_and_recurring_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        client.post(
            "/v1/orchestrations",
            json={
                "orchestration_id": "orc_observability",
                "name": "Observability orchestration",
                "version": "1.0.0",
                "status": "published",
                "entrypoint": "codex://orchestrations/observability",
                "required_tools": ["shell"],
                "required_skills": [],
                "policy_profile": "default",
                "compatibility": ["cli"],
                "published_at": "2026-04-09T18:00:00Z",
            },
        )
        register_response = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["shell"],
                "machine_id": "machine_observability",
            },
        )
        headers = {"X-Instance-Token": register_response.json()["instance_token"]}
        instance_id = register_response.json()["instance_id"]

        for index, error_payload in enumerate(
            [
                {"error_category": "network_timeout", "category": "network_timeout"},
                {"error_category": "network_timeout", "category": "network_timeout"},
                {"code": "shell_exit_1"},
                {},
            ],
            start=1,
        ):
            run_response = client.post(
                "/v1/runs",
                headers=headers,
                json={
                    "orchestration_id": "orc_observability",
                    "instance_id": instance_id,
                    "title": "Recurring sync workflow",
                    "goal": "Surface recurring workflow and errors.",
                    "workspace_path": "D:/Code/Manged-agent",
                    "trigger": "manual",
                },
            )
            run_id = run_response.json()["run_id"]
            task_id = run_response.json()["task_id"]
            events = [
                {
                    "event_id": f"evt_{index}aaaabbbb",
                    "run_id": run_id,
                    "task_id": task_id,
                    "source": "codex",
                    "type": "run.started",
                    "timestamp": f"2026-04-09T18:0{index}:00Z",
                    "payload": {"task_title": "Recurring sync workflow"},
                },
                {
                    "event_id": f"evt_{index}ccccdddd",
                    "run_id": run_id,
                    "task_id": task_id,
                    "source": "codex",
                    "type": "error.raised",
                    "timestamp": f"2026-04-09T18:0{index}:10Z",
                    "payload": {"task_title": "Recurring sync workflow", **error_payload},
                },
            ]
            batch_response = client.post(
                f"/v1/runs/{run_id}/events:batch",
                headers=headers,
                json={"events": events},
            )
            assert batch_response.status_code == 202
            complete_response = client.post(
                f"/v1/runs/{run_id}/complete",
                headers=headers,
                json={
                    "status": "failed",
                    "summary": "Run failed for observability.",
                    "ended_at": f"2026-04-09T18:0{index}:30Z",
                },
            )
            assert complete_response.status_code == 200

        overview_response = client.get("/v1/dashboard/overview")
        assert overview_response.status_code == 200
        overview_payload = overview_response.json()

        assert overview_payload["recent_error_count"] == 4
        assert overview_payload["top_workflows"][0]["title_pattern"] == "Recurring sync workflow"
        assert overview_payload["top_workflows"][0]["occurrence_count"] == 2
        assert overview_payload["top_workflows"][0]["error_categories"] == ["network_timeout"]

        error_breakdown = {item["category"]: item for item in overview_payload["error_breakdown"]}
        assert error_breakdown["network_timeout"]["occurrence_count"] == 2
        assert error_breakdown["network_timeout"]["affected_orchestration_ids"] == ["orc_observability"]
        assert error_breakdown["shell_exit_1"]["occurrence_count"] == 1
        assert error_breakdown["uncategorized"]["occurrence_count"] == 1

        dashboard_page = client.get("/dashboard")
        assert dashboard_page.status_code == 200
        assert "Managed Agent Command Center" in dashboard_page.text


def test_dashboard_workflow_and_error_drilldown_json_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        client.post(
            "/v1/orchestrations",
            json={
                "orchestration_id": "orc_drilldown",
                "name": "Drilldown orchestration",
                "version": "1.0.0",
                "status": "published",
                "entrypoint": "codex://orchestrations/drilldown",
                "required_tools": ["shell"],
                "required_skills": [],
                "policy_profile": "default",
                "compatibility": ["cli"],
                "published_at": "2026-04-09T18:00:00Z",
            },
        )
        register_response = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["shell"],
                "machine_id": "machine_drilldown",
            },
        )
        headers = {"X-Instance-Token": register_response.json()["instance_token"]}
        instance_id = register_response.json()["instance_id"]

        created_runs: list[str] = []
        for index, error_payload in enumerate(
            [
                {"error_category": "network_timeout", "category": "network_timeout", "message": "network timeout one"},
                {"error_category": "network_timeout", "category": "network_timeout", "message": "network timeout two"},
                {"code": "shell_exit_1", "error": "shell exit one"},
            ],
            start=1,
        ):
            run_response = client.post(
                "/v1/runs",
                headers=headers,
                json={
                    "orchestration_id": "orc_drilldown",
                    "instance_id": instance_id,
                    "title": "Drilldown workflow",
                    "goal": "Expose workflow and error drilldown.",
                    "workspace_path": "D:/Code/Manged-agent",
                    "trigger": "manual",
                },
            )
            run_id = run_response.json()["run_id"]
            task_id = run_response.json()["task_id"]
            created_runs.append(run_id)
            batch_response = client.post(
                f"/v1/runs/{run_id}/events:batch",
                headers=headers,
                json={
                    "events": [
                        {
                            "event_id": f"evt_dd{index}aaaab",
                            "run_id": run_id,
                            "task_id": task_id,
                            "source": "codex",
                            "type": "run.started",
                            "timestamp": f"2026-04-09T18:1{index}:00Z",
                            "payload": {"task_title": "Drilldown workflow", "step_name": "collect"},
                        },
                        {
                            "event_id": f"evt_dd{index}bbbcc",
                            "run_id": run_id,
                            "task_id": task_id,
                            "source": "codex",
                            "type": "tool.called",
                            "timestamp": f"2026-04-09T18:1{index}:05Z",
                            "payload": {"task_title": "Drilldown workflow", "tool_name": "shell", "input_summary": "echo test"},
                        },
                        {
                            "event_id": f"evt_dd{index}cccdd",
                            "run_id": run_id,
                            "task_id": task_id,
                            "source": "codex",
                            "type": "error.raised",
                            "timestamp": f"2026-04-09T18:1{index}:10Z",
                            "payload": {"task_title": "Drilldown workflow", **error_payload},
                        },
                    ]
                },
            )
            assert batch_response.status_code == 202
            complete_response = client.post(
                f"/v1/runs/{run_id}/complete",
                headers=headers,
                json={
                    "status": "failed",
                    "summary": "Drilldown failed.",
                    "ended_at": f"2026-04-09T18:1{index}:30Z",
                },
            )
            assert complete_response.status_code == 200

        overview = client.get("/v1/dashboard/overview")
        fingerprint_id = overview.json()["top_workflows"][0]["fingerprint_id"]

        workflows_response = client.get("/v1/dashboard/workflows", params={"orchestration_id": "orc_drilldown", "terminal_status": "failed", "limit": 1})
        assert workflows_response.status_code == 200
        workflows_payload = workflows_response.json()
        assert len(workflows_payload) == 1
        assert workflows_payload[0]["fingerprint_id"] == fingerprint_id
        assert workflows_payload[0]["last_run_id"] in created_runs[:2]
        assert workflows_payload[0]["latest_task_title"] == "Drilldown workflow"

        workflow_detail = client.get(f"/v1/dashboard/workflows/{fingerprint_id}")
        assert workflow_detail.status_code == 200
        assert workflow_detail.json()["workflow"]["fingerprint_id"] == fingerprint_id
        assert workflow_detail.json()["step_signature"][0] == "run.started"
        assert workflow_detail.json()["tool_signature"] == ["shell"]
        assert len(workflow_detail.json()["recent_runs"]) >= 2

        errors_response = client.get("/v1/dashboard/errors", params={"orchestration_id": "orc_drilldown", "instance_id": instance_id, "limit": 5})
        assert errors_response.status_code == 200
        errors_payload = {item["category"]: item for item in errors_response.json()}
        assert errors_payload["network_timeout"]["occurrence_count"] == 2
        assert errors_payload["network_timeout"]["last_run_id"] in created_runs[:2]
        assert errors_payload["network_timeout"]["sample_messages"] == ["network timeout two", "network timeout one"]
        assert errors_payload["shell_exit_1"]["occurrence_count"] == 1

        error_detail = client.get("/v1/dashboard/errors/network_timeout", params={"instance_id": instance_id})
        assert error_detail.status_code == 200
        assert error_detail.json()["category"] == "network_timeout"
        assert len(error_detail.json()["recent_runs"]) == 2
        assert error_detail.json()["sample_messages"] == ["network timeout two", "network timeout one"]


def test_dashboard_spa_shell_handles_workflow_error_and_run_deep_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        client.post(
            "/v1/orchestrations",
            json={
                "orchestration_id": "orc_html_drilldown",
                "name": "HTML drilldown orchestration",
                "version": "1.0.0",
                "status": "published",
                "entrypoint": "codex://orchestrations/html-drilldown",
                "required_tools": ["shell"],
                "required_skills": [],
                "policy_profile": "default",
                "compatibility": ["cli"],
                "published_at": "2026-04-09T18:00:00Z",
            },
        )
        register_response = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["shell"],
                "machine_id": "machine_html_drilldown",
            },
        )
        headers = {"X-Instance-Token": register_response.json()["instance_token"]}
        run_response = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_html_drilldown",
                "instance_id": register_response.json()["instance_id"],
                "title": "HTML workflow",
                "goal": "Render workflow and error pages.",
                "workspace_path": "D:/Code/Manged-agent",
                "trigger": "manual",
            },
        )
        run_id = run_response.json()["run_id"]
        task_id = run_response.json()["task_id"]
        client.post(
            f"/v1/runs/{run_id}/events:batch",
            headers=headers,
            json={
                "events": [
                    {
                        "event_id": "evt_htmlaaaa1",
                        "run_id": run_id,
                        "task_id": task_id,
                        "source": "codex",
                        "type": "run.started",
                        "timestamp": "2026-04-09T18:21:00Z",
                        "payload": {"task_title": "HTML workflow", "step_name": "collect"},
                    },
                    {
                        "event_id": "evt_htmlbbbb2",
                        "run_id": run_id,
                        "task_id": task_id,
                        "source": "codex",
                        "type": "error.raised",
                        "timestamp": "2026-04-09T18:21:10Z",
                        "payload": {"task_title": "HTML workflow", "error_category": "network_timeout", "message": "network html"},
                    },
                ]
            },
        )
        client.post(
            f"/v1/runs/{run_id}/complete",
            headers=headers,
            json={
                "status": "failed",
                "summary": "HTML drilldown failed.",
                "ended_at": "2026-04-09T18:21:30Z",
            },
        )

        overview = client.get("/v1/dashboard/overview")
        fingerprint_id = overview.json()["top_workflows"][0]["fingerprint_id"]

        overview_page = client.get("/dashboard")
        workflows_page = client.get("/dashboard/workflows")
        workflow_detail_page = client.get(f"/dashboard/workflows/{fingerprint_id}")
        errors_page = client.get("/dashboard/errors")
        error_detail_page = client.get("/dashboard/errors/network_timeout")
        run_detail_page = client.get(f"/dashboard/runs/{run_id}")

        assert overview_page.status_code == 200
        assert workflows_page.status_code == 200
        assert workflow_detail_page.status_code == 200
        assert errors_page.status_code == 200
        assert error_detail_page.status_code == 200
        assert run_detail_page.status_code == 200
        assert "Managed Agent Command Center" in overview_page.text
        assert "Managed Agent Command Center" in workflows_page.text
        assert "Managed Agent Command Center" in workflow_detail_page.text
        assert "Managed Agent Command Center" in errors_page.text
        assert "Managed Agent Command Center" in error_detail_page.text
        assert "Managed Agent Command Center" in run_detail_page.text
