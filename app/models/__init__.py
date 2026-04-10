from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ClientKind = Literal["ide", "cli", "windows_app"]
OrchestrationStatus = Literal["draft", "published", "archived"]
RunStatus = Literal["pending", "running", "blocked", "completed", "failed"]
TaskStatus = Literal["pending", "running", "blocked", "completed", "failed"]
EventSource = Literal["codex", "platform", "tool", "policy"]
RunEventType = Literal[
    "run.started",
    "task.started",
    "step.started",
    "step.completed",
    "tool.called",
    "tool.completed",
    "policy.requested",
    "policy.blocked",
    "error.raised",
    "heartbeat",
    "run.completed",
    "run.failed",
]
SensitiveActionType = Literal[
    "write_outside_workspace",
    "mass_delete_or_move",
    "destructive_shell",
    "git_push",
    "outbound_network",
    "unapproved_dependency_or_binary",
]
PolicyDecisionValue = Literal["allow", "deny", "require_approval"]
PolicyDecisionStatus = Literal["pending", "approved", "denied", "resolved_allow", "resolved_deny"]
PolicyResolutionValue = Literal["approved", "denied"]
TerminalRunStatus = Literal["completed", "failed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterInstanceRequest(StrictModel):
    client_kind: ClientKind
    workspace_path: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    machine_id: str = Field(min_length=1)


class RegisterInstanceResponse(StrictModel):
    instance_id: str = Field(pattern=r"^inst_[a-z0-9]{8,64}$")
    instance_token: str = Field(pattern=r"^itok_[a-z0-9]{8,64}$")
    registered_at: datetime


class CodexInstance(StrictModel):
    instance_id: str = Field(pattern=r"^inst_[a-z0-9]{8,64}$")
    machine_id: str = Field(min_length=1)
    client_kind: ClientKind
    workspace_path: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    registered_at: datetime
    last_seen_at: datetime
    instance_token: str = Field(pattern=r"^itok_[a-z0-9]{8,64}$")


class Orchestration(StrictModel):
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: OrchestrationStatus
    entrypoint: str = Field(min_length=1)
    required_tools: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    policy_profile: str = Field(min_length=1)
    compatibility: list[ClientKind] = Field(default_factory=list)
    published_at: datetime | None = None

    @model_validator(mode="after")
    def validate_published_timestamp(self) -> "Orchestration":
        if self.status == "published" and self.published_at is None:
            raise ValueError("published orchestrations require published_at")
        return self


class StartRunRequest(StrictModel):
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    instance_id: str = Field(pattern=r"^inst_[a-z0-9]{8,64}$")
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    trigger: str = Field(min_length=1)


class StartRunResponse(StrictModel):
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    policy_profile: str = Field(min_length=1)
    started_at: datetime


class Run(StrictModel):
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    orchestration_version: str = Field(min_length=1)
    instance_id: str = Field(pattern=r"^inst_[a-z0-9]{8,64}$")
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    trigger: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    summary: str | None = None


class RunTask(StrictModel):
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    status: TaskStatus
    current_step: str | None = None
    started_at: datetime
    ended_at: datetime | None = None


class RunEvent(StrictModel):
    event_id: str = Field(pattern=r"^evt_[a-z0-9]{8,64}$")
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    source: EventSource
    type: RunEventType
    timestamp: datetime
    payload: dict[str, object] = Field(default_factory=dict)


class BatchRunEventsRequest(StrictModel):
    events: list[RunEvent] = Field(min_length=1)


class ToolExecution(StrictModel):
    tool_execution_id: str = Field(pattern=r"^tex_[a-z0-9]{8,64}$")
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    tool_name: str = Field(min_length=1)
    status: Literal["called", "completed", "failed"]
    started_at: datetime
    ended_at: datetime | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    error_summary: str | None = None


class PreauthorizeActionRequest(StrictModel):
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    action_type: SensitiveActionType
    target: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class PolicyDecision(StrictModel):
    decision_id: str = Field(pattern=r"^dec_[a-z0-9]{8,64}$")
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    action_type: SensitiveActionType
    decision: PolicyDecisionValue
    reason: str = Field(min_length=1)
    status: PolicyDecisionStatus
    requested_at: datetime
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    comment: str | None = None


class PolicyDecisionResolutionRequest(StrictModel):
    resolution: PolicyResolutionValue
    resolved_by: str = Field(min_length=1)
    comment: str | None = None


class CompleteRunRequest(StrictModel):
    status: TerminalRunStatus
    summary: str | None = None
    ended_at: datetime


class WorkflowFingerprint(StrictModel):
    fingerprint_id: str = Field(pattern=r"^wfp_[a-z0-9]{8,64}$")
    title_pattern: str = Field(min_length=1)
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    step_signature: list[str] = Field(default_factory=list)
    tool_signature: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(ge=1)
    last_seen_at: datetime
    terminal_status: TerminalRunStatus
    error_categories: list[str] = Field(default_factory=list)


class SyncOrchestrationsResponse(StrictModel):
    orchestrations: list[Orchestration] = Field(default_factory=list)
    synced_at: datetime


class DashboardWorkflowSummary(StrictModel):
    fingerprint_id: str = Field(pattern=r"^wfp_[a-z0-9]{8,64}$")
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    title_pattern: str = Field(min_length=1)
    occurrence_count: int = Field(ge=1)
    terminal_status: TerminalRunStatus
    error_categories: list[str] = Field(default_factory=list)
    last_seen_at: datetime
    last_run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    latest_task_title: str = Field(min_length=1)


class DashboardErrorSummary(StrictModel):
    category: str = Field(min_length=1)
    occurrence_count: int = Field(ge=1)
    affected_orchestration_ids: list[str] = Field(default_factory=list)
    last_seen_at: datetime
    last_run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    sample_messages: list[str] = Field(default_factory=list)


class DashboardRunSummary(StrictModel):
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    task_title: str = Field(min_length=1)


class DashboardWorkflowDetail(StrictModel):
    workflow: DashboardWorkflowSummary
    recent_runs: list[DashboardRunSummary] = Field(default_factory=list)
    step_signature: list[str] = Field(default_factory=list)
    tool_signature: list[str] = Field(default_factory=list)


class DashboardErrorDetail(StrictModel):
    category: str = Field(min_length=1)
    occurrence_count: int = Field(ge=1)
    affected_orchestration_ids: list[str] = Field(default_factory=list)
    recent_runs: list[DashboardRunSummary] = Field(default_factory=list)
    sample_messages: list[str] = Field(default_factory=list)


class DashboardOverviewResponse(StrictModel):
    orchestration_count: int = Field(ge=0)
    active_instance_count: int = Field(ge=0)
    running_run_count: int = Field(ge=0)
    blocked_run_count: int = Field(ge=0)
    recent_error_count: int = Field(ge=0)
    pending_policy_decision_count: int = Field(ge=0)
    top_workflows: list[DashboardWorkflowSummary] = Field(default_factory=list)
    error_breakdown: list[DashboardErrorSummary] = Field(default_factory=list)


class DashboardRunDetail(StrictModel):
    run: Run
    task: RunTask
    events: list[RunEvent] = Field(default_factory=list)
    tool_executions: list[ToolExecution] = Field(default_factory=list)
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    fingerprint: WorkflowFingerprint | None = None
    orchestration: Orchestration | None = None
    instance: CodexInstance | None = None


class CommandCenterExecutiveMetrics(StrictModel):
    active_runs: int = Field(ge=0)
    blocked_runs: int = Field(ge=0)
    pending_approvals: int = Field(ge=0)
    recent_errors: int = Field(ge=0)
    connected_agents: int = Field(ge=0)


class CommandCenterRuntimeInfo(StrictModel):
    local_instance_id: str = Field(pattern=r"^inst_[a-z0-9]{8,64}$")
    local_instance_workspace_path: str = Field(min_length=1)
    admin_auth_required: bool
    app_mode: Literal["local", "lan"]
    poll_interval_seconds: int = Field(ge=1)


class CommandCenterProject(StrictModel):
    project_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    run_count: int = Field(ge=0)
    active_run_count: int = Field(ge=0)
    blocked_run_count: int = Field(ge=0)
    pending_approval_count: int = Field(ge=0)
    recent_error_count: int = Field(ge=0)


class CommandCenterRunItem(StrictModel):
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    orchestration_name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    status: RunStatus
    current_step: str | None = None
    summary: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    workspace_path: str = Field(min_length=1)
    has_pending_approval: bool = False
    error_categories: list[str] = Field(default_factory=list)
    workflow_fingerprint_id: str | None = None


class CommandCenterApprovalItem(StrictModel):
    decision_id: str = Field(pattern=r"^dec_[a-z0-9]{8,64}$")
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    task_id: str = Field(pattern=r"^task_[a-z0-9]{8,64}$")
    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    action_type: SensitiveActionType
    reason: str = Field(min_length=1)
    requested_at: datetime


class CommandCenterErrorItem(StrictModel):
    category: str = Field(min_length=1)
    run_id: str = Field(pattern=r"^run_[a-z0-9]{8,64}$")
    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    message: str | None = None
    last_seen_at: datetime


class CommandCenterQueues(StrictModel):
    in_progress: list[CommandCenterRunItem] = Field(default_factory=list)
    blocked: list[CommandCenterRunItem] = Field(default_factory=list)
    needs_attention: list[CommandCenterRunItem] = Field(default_factory=list)
    recent: list[CommandCenterRunItem] = Field(default_factory=list)


class CommandCenterUrgentItems(StrictModel):
    approvals: list[CommandCenterApprovalItem] = Field(default_factory=list)
    blocked_runs: list[CommandCenterRunItem] = Field(default_factory=list)
    errors: list[CommandCenterErrorItem] = Field(default_factory=list)


class DashboardCommandCenterResponse(StrictModel):
    executive: CommandCenterExecutiveMetrics
    runtime: CommandCenterRuntimeInfo
    projects: list[CommandCenterProject] = Field(default_factory=list)
    queues: CommandCenterQueues
    urgent: CommandCenterUrgentItems
    available_orchestrations: list[Orchestration] = Field(default_factory=list)


class DashboardLaunchRunRequest(StrictModel):
    orchestration_id: str = Field(pattern=r"^orc_[a-z0-9_]{3,128}$")
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    trigger: str = Field(min_length=1)


class DashboardRelaunchRunRequest(StrictModel):
    title: str | None = None
    goal: str | None = None
    workspace_path: str | None = None
    trigger: str | None = None


class EventBatchAcceptedResponse(StrictModel):
    accepted: int = Field(ge=0)


class OperationStatusResponse(StrictModel):
    status: str = Field(min_length=1)

__all__ = [
    "BatchRunEventsRequest",
    "ClientKind",
    "CodexInstance",
    "CompleteRunRequest",
    "DashboardErrorDetail",
    "DashboardErrorSummary",
    "DashboardCommandCenterResponse",
    "DashboardOverviewResponse",
    "DashboardLaunchRunRequest",
    "DashboardRelaunchRunRequest",
    "DashboardRunDetail",
    "DashboardRunSummary",
    "DashboardWorkflowDetail",
    "DashboardWorkflowSummary",
    "CommandCenterApprovalItem",
    "CommandCenterErrorItem",
    "CommandCenterExecutiveMetrics",
    "CommandCenterProject",
    "CommandCenterQueues",
    "CommandCenterRunItem",
    "CommandCenterRuntimeInfo",
    "CommandCenterUrgentItems",
    "EventBatchAcceptedResponse",
    "OperationStatusResponse",
    "Orchestration",
    "OrchestrationStatus",
    "PolicyDecision",
    "PolicyDecisionResolutionRequest",
    "PolicyDecisionStatus",
    "PolicyDecisionValue",
    "PreauthorizeActionRequest",
    "RegisterInstanceRequest",
    "RegisterInstanceResponse",
    "Run",
    "RunEvent",
    "RunEventType",
    "RunStatus",
    "RunTask",
    "SensitiveActionType",
    "StartRunRequest",
    "StartRunResponse",
    "SyncOrchestrationsResponse",
    "TaskStatus",
    "ToolExecution",
    "WorkflowFingerprint",
]
