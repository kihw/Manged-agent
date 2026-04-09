from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    BatchRunEventsRequest,
    CodexInstance,
    CompleteRunRequest,
    Orchestration,
    PolicyDecision,
    PolicyDecisionResolutionRequest,
    PreauthorizeActionRequest,
    RegisterInstanceRequest,
    RegisterInstanceResponse,
    Run,
    RunEvent,
    RunStatus,
    RunTask,
    StartRunRequest,
    StartRunResponse,
    ToolExecution,
    WorkflowFingerprint,
)


def test_register_instance_round_trip() -> None:
    payload = {
        "client_kind": "cli",
        "workspace_path": "D:/Code/Manged-agent",
        "capabilities": ["shell", "git"],
        "machine_id": "machine_devbox",
    }

    request = RegisterInstanceRequest.model_validate(payload)
    response = RegisterInstanceResponse(
        instance_id="inst_1234abcd",
        instance_token="itok_1234abcd",
        registered_at=datetime(2026, 4, 9, tzinfo=UTC),
    )

    assert request.model_dump() == payload
    assert response.instance_id.startswith("inst_")
    assert response.instance_token.startswith("itok_")


def test_orchestration_requires_published_metadata() -> None:
    orchestration = Orchestration.model_validate(
        {
            "orchestration_id": "orc_sync_repo",
            "name": "Sync repository",
            "version": "1.0.0",
            "status": "published",
            "entrypoint": "codex://orchestrations/sync-repo",
            "required_tools": ["shell"],
            "required_skills": ["planning"],
            "policy_profile": "default",
            "compatibility": ["cli", "windows_app"],
            "published_at": "2026-04-09T18:00:00Z",
        }
    )

    assert orchestration.status == "published"
    assert orchestration.compatibility == ["cli", "windows_app"]

    with pytest.raises(ValidationError):
        Orchestration.model_validate({"orchestration_id": "orc_sync_repo"})


def test_start_run_request_keeps_explicit_title_and_goal() -> None:
    request = StartRunRequest.model_validate(
        {
            "orchestration_id": "orc_sync_repo",
            "instance_id": "inst_1234abcd",
            "title": "Synchroniser les examples OpenAPI",
            "goal": "Publier un exemple plus clair pour les runs V1.",
            "workspace_path": "D:/Code/Manged-agent",
            "trigger": "manual",
        }
    )
    response = StartRunResponse(
        run_id="run_1234abcd",
        task_id="task_1234abcd",
        policy_profile="default",
        started_at=datetime(2026, 4, 9, tzinfo=UTC),
    )

    assert request.title == "Synchroniser les examples OpenAPI"
    assert request.goal.startswith("Publier")
    assert response.task_id.startswith("task_")


def test_run_event_batch_supports_canonical_event_types() -> None:
    event = RunEvent.model_validate(
        {
            "event_id": "evt_1234abcd",
            "run_id": "run_1234abcd",
            "task_id": "task_1234abcd",
            "source": "codex",
            "type": "tool.called",
            "timestamp": "2026-04-09T18:00:00Z",
            "payload": {
                "task_title": "Synchroniser les examples OpenAPI",
                "step_name": "publish_openapi",
                "tool_name": "shell",
            },
        }
    )
    batch = BatchRunEventsRequest(events=[event])

    assert batch.events[0].type == "tool.called"
    assert batch.events[0].payload["task_title"] == "Synchroniser les examples OpenAPI"

    with pytest.raises(ValidationError):
        RunEvent.model_validate(
            {
                "event_id": "evt_1234abcd",
                "run_id": "run_1234abcd",
                "task_id": "task_1234abcd",
                "source": "codex",
                "type": "unknown.event",
                "timestamp": "2026-04-09T18:00:00Z",
                "payload": {},
            }
        )


def test_preauthorize_request_and_policy_resolution_shapes() -> None:
    request = PreauthorizeActionRequest.model_validate(
        {
            "run_id": "run_1234abcd",
            "task_id": "task_1234abcd",
            "action_type": "outbound_network",
            "target": "https://api.example.dev/packages",
            "workspace_path": "D:/Code/Manged-agent",
            "tool_name": "http",
            "metadata": {"method": "GET"},
        }
    )
    decision = PolicyDecision.model_validate(
        {
            "decision_id": "dec_1234abcd",
            "run_id": "run_1234abcd",
            "task_id": "task_1234abcd",
            "action_type": "outbound_network",
            "decision": "require_approval",
            "reason": "Outbound network is sensitive in V1.",
            "status": "pending",
            "requested_at": "2026-04-09T18:00:00Z",
            "expires_at": "2026-04-09T18:15:00Z",
        }
    )
    resolution = PolicyDecisionResolutionRequest.model_validate(
        {
            "resolution": "approved",
            "resolved_by": "operator",
            "comment": "Allowed for package metadata lookup.",
        }
    )

    assert request.action_type == "outbound_network"
    assert decision.status == "pending"
    assert resolution.resolution == "approved"


def test_run_and_fingerprint_round_trip() -> None:
    run = Run.model_validate(
        {
            "run_id": "run_1234abcd",
            "orchestration_id": "orc_sync_repo",
            "orchestration_version": "1.0.0",
            "instance_id": "inst_1234abcd",
            "status": "running",
            "started_at": "2026-04-09T18:00:00Z",
            "ended_at": None,
            "trigger": "manual",
            "workspace_path": "D:/Code/Manged-agent",
            "summary": None,
        }
    )
    task = RunTask.model_validate(
        {
            "task_id": "task_1234abcd",
            "run_id": "run_1234abcd",
            "title": "Synchroniser les examples OpenAPI",
            "goal": "Mettre a jour les events de run.",
            "status": "running",
            "current_step": "publish_openapi",
            "started_at": "2026-04-09T18:00:00Z",
            "ended_at": None,
        }
    )
    tool_execution = ToolExecution.model_validate(
        {
            "tool_execution_id": "tex_1234abcd",
            "run_id": "run_1234abcd",
            "task_id": "task_1234abcd",
            "tool_name": "shell",
            "status": "completed",
            "started_at": "2026-04-09T18:01:00Z",
            "ended_at": "2026-04-09T18:01:03Z",
            "input_summary": "python scripts/validate_openapi_spec.py",
            "output_summary": "spec valid",
            "error_summary": None,
        }
    )
    fingerprint = WorkflowFingerprint.model_validate(
        {
            "fingerprint_id": "wfp_1234abcd",
            "title_pattern": "Synchroniser les examples OpenAPI",
            "orchestration_id": "orc_sync_repo",
            "step_signature": ["task.started", "step.started", "tool.called", "tool.completed", "run.completed"],
            "tool_signature": ["shell"],
            "occurrence_count": 2,
            "last_seen_at": "2026-04-09T18:05:00Z",
            "terminal_status": "completed",
            "error_categories": [],
        }
    )

    assert run.status == "running"
    assert task.title.startswith("Synchroniser")
    assert tool_execution.output_summary == "spec valid"
    assert fingerprint.terminal_status == "completed"


def test_complete_run_request_requires_terminal_status() -> None:
    request = CompleteRunRequest.model_validate(
        {
            "status": "completed",
            "summary": "Run completed successfully.",
            "ended_at": "2026-04-09T18:10:00Z",
        }
    )
    assert request.status == "completed"

    with pytest.raises(ValidationError):
        CompleteRunRequest.model_validate(
            {
                "status": "running",
                "summary": "still going",
                "ended_at": "2026-04-09T18:10:00Z",
            }
        )


def test_run_status_aliases_are_not_accepted() -> None:
    assert RunStatus.__args__ == ("pending", "running", "blocked", "completed", "failed")

