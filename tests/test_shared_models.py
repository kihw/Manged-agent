import pytest
from pydantic import ValidationError

from app.models import AgentDefinition, AgentTask, AuthContext, Limits
from app.models.shared import can_transition_approval_status


def test_agent_definition_roundtrip_required_fields() -> None:
    payload = {
        "agent_id": "agent_planner",
        "version": "2.1.0",
        "system_prompt": "You are a planning assistant.",
        "tools": ["git", "shell"],
        "policy_profile": "strict",
        "limits": {
            "max_iterations": 40,
            "max_input_tokens": 64000,
            "max_output_tokens": 8000,
            "max_cost_usd": 3.5,
            "max_duration_sec": 1800,
        },
    }

    model = AgentDefinition.model_validate(payload)
    dumped = model.model_dump()

    assert dumped["agent_id"] == payload["agent_id"]
    assert dumped["limits"] == Limits.model_validate(payload["limits"]).model_dump()


def test_agent_definition_requires_expected_fields() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate({"agent_id": "agent_planner"})


def test_agent_task_roundtrip_required_fields() -> None:
    payload = {
        "task_id": "task_0f14ab66",
        "trace_id": "trace_dcf98ba1",
        "agent_id": "agent_planner",
        "goal": "Update OpenAPI examples",
        "repo_path": "/workspace/Manged-agent",
        "status": "queued",
    }

    model = AgentTask.model_validate(payload)
    dumped = model.model_dump()

    assert dumped["task_id"] == payload["task_id"]
    assert dumped["trace_id"] == payload["trace_id"]
    assert dumped["steps"] == []
    assert dumped["tool_executions"] == []
    assert dumped["approval_requests"] == []
    assert dumped["artifacts"] == []


def test_agent_task_requires_expected_fields() -> None:
    with pytest.raises(ValidationError):
        AgentTask.model_validate({"task_id": "task_0f14ab66"})


def test_auth_context_roundtrip_and_required_mode() -> None:
    payload = {"mode": "oauth", "user_id": "user_1234", "tenant_id": "tenant_acme"}

    model = AuthContext.model_validate(payload)
    dumped = model.model_dump()

    assert dumped == payload

    with pytest.raises(ValidationError):
        AuthContext.model_validate({"user_id": "user_1234"})


@pytest.mark.parametrize("target_status", ["approved", "rejected", "expired"])
def test_approval_status_transitions_from_pending(target_status: str) -> None:
    assert can_transition_approval_status("pending", target_status) is True


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("approved", "rejected"),
        ("rejected", "approved"),
        ("expired", "approved"),
    ],
)
def test_approval_status_transitions_terminal_states_are_not_mutable(
    current_status: str, target_status: str
) -> None:
    assert can_transition_approval_status(current_status, target_status) is False
