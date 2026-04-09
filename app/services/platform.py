from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json

from fastapi import status

from app.models import (
    BatchRunEventsRequest,
    CodexInstance,
    CompleteRunRequest,
    DashboardErrorSummary,
    DashboardOverviewResponse,
    DashboardRunDetail,
    DashboardWorkflowSummary,
    EventBatchAcceptedResponse,
    OperationStatusResponse,
    Orchestration,
    PolicyDecision,
    PolicyDecisionResolutionRequest,
    PreauthorizeActionRequest,
    RegisterInstanceRequest,
    RegisterInstanceResponse,
    Run,
    RunEvent,
    RunTask,
    StartRunRequest,
    StartRunResponse,
    SyncOrchestrationsResponse,
    ToolExecution,
    WorkflowFingerprint,
)
from app.routers.errors import ApiError
from app.services.settings import AppSettings, new_public_id
from app.services.storage import PlatformStore, PostgresPlatformStore, SQLitePlatformStore, utc_now


class PlatformService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.store = self._build_store()

    def _build_store(self) -> PlatformStore:
        if self.settings.storage_backend == "postgres":
            if not self.settings.database_url:
                raise RuntimeError("DATABASE_URL is required for postgres backend.")
            return PostgresPlatformStore(self.settings.database_url)
        return SQLitePlatformStore(self.settings.db_path)

    def publish_orchestration(self, orchestration: Orchestration) -> Orchestration:
        return self.store.save_orchestration(orchestration)

    def get_orchestration(self, orchestration_id: str) -> Orchestration:
        orchestration = self.store.get_orchestration(orchestration_id)
        if orchestration is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "orchestration_not_found", "Orchestration was not found.")
        return orchestration

    def register_instance(self, payload: RegisterInstanceRequest) -> RegisterInstanceResponse:
        now = utc_now()
        instance = CodexInstance(
            instance_id=new_public_id("inst"),
            instance_token=new_public_id("itok"),
            machine_id=payload.machine_id,
            client_kind=payload.client_kind,
            workspace_path=payload.workspace_path,
            capabilities=payload.capabilities,
            registered_at=now,
            last_seen_at=now,
        )
        self.store.save_instance(instance)
        return RegisterInstanceResponse(
            instance_id=instance.instance_id,
            instance_token=instance.instance_token,
            registered_at=instance.registered_at,
        )

    def authenticate_instance(self, instance_token: str | None) -> CodexInstance:
        if not instance_token:
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "missing_instance_token", "X-Instance-Token is required.")
        instance = self.store.get_instance_by_token(instance_token)
        if instance is None:
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_instance_token", "Unknown Codex instance token.")
        instance.last_seen_at = utc_now()
        self.store.save_instance(instance)
        return instance

    def sync_orchestrations(self, instance: CodexInstance) -> SyncOrchestrationsResponse:
        orchestrations = [
            orchestration
            for orchestration in self.store.list_orchestrations()
            if orchestration.status == "published"
            and (not orchestration.compatibility or instance.client_kind in orchestration.compatibility)
        ]
        return SyncOrchestrationsResponse(orchestrations=orchestrations, synced_at=utc_now())

    def start_run(self, payload: StartRunRequest, instance: CodexInstance) -> StartRunResponse:
        if payload.instance_id != instance.instance_id:
            raise ApiError(status.HTTP_409_CONFLICT, "instance_mismatch", "Run must be started by the registered instance.")
        orchestration = self.get_orchestration(payload.orchestration_id)
        now = utc_now()
        run = Run(
            run_id=new_public_id("run"),
            orchestration_id=orchestration.orchestration_id,
            orchestration_version=orchestration.version,
            instance_id=instance.instance_id,
            status="pending",
            started_at=now,
            trigger=payload.trigger,
            workspace_path=payload.workspace_path,
            summary=None,
        )
        task = RunTask(
            task_id=new_public_id("task"),
            run_id=run.run_id,
            title=payload.title,
            goal=payload.goal,
            status="pending",
            current_step=None,
            started_at=now,
            ended_at=None,
        )
        self.store.save_run(run)
        self.store.save_task(task)
        return StartRunResponse(
            run_id=run.run_id,
            task_id=task.task_id,
            policy_profile=orchestration.policy_profile,
            started_at=run.started_at,
        )

    def emit_events(self, run_id: str, payload: BatchRunEventsRequest, instance: CodexInstance) -> EventBatchAcceptedResponse:
        run = self._get_run_owned_by_instance(run_id, instance.instance_id)
        task = self._get_single_task_for_run(run.run_id)
        for event in payload.events:
            if event.run_id != run_id or event.task_id != task.task_id:
                raise ApiError(status.HTTP_409_CONFLICT, "event_run_mismatch", "Event identifiers do not match the target run.")
            self.store.save_event(event)
            task_title = event.payload.get("task_title")
            if isinstance(task_title, str) and task.title != task_title:
                task.title = task_title
            step_name = event.payload.get("step_name")
            if isinstance(step_name, str):
                task.current_step = step_name
            if event.type in {"run.started", "task.started", "step.started"}:
                run.status = "running"
                task.status = "running"
            if event.type == "policy.blocked":
                run.status = "blocked"
                task.status = "blocked"
            if event.type == "tool.called":
                self._record_tool_called(event)
            if event.type == "tool.completed":
                self._record_tool_completed(event)
        self.store.save_run(run)
        self.store.save_task(task)
        return EventBatchAcceptedResponse(accepted=len(payload.events))

    def preauthorize_action(self, payload: PreauthorizeActionRequest, instance: CodexInstance) -> PolicyDecision:
        self._get_run_owned_by_instance(payload.run_id, instance.instance_id)
        self._get_task(payload.task_id)
        now = utc_now()
        decision_value = self._evaluate_sensitive_action(payload)
        decision = PolicyDecision(
            decision_id=new_public_id("dec"),
            run_id=payload.run_id,
            task_id=payload.task_id,
            action_type=payload.action_type,
            decision=decision_value,
            reason=self._decision_reason(payload.action_type, decision_value),
            status="pending" if decision_value == "require_approval" else ("resolved_allow" if decision_value == "allow" else "resolved_deny"),
            requested_at=now,
            expires_at=now + timedelta(minutes=15) if decision_value == "require_approval" else None,
            resolved_at=None if decision_value == "require_approval" else now,
            resolved_by=None,
            comment=None,
        )
        self.store.save_policy_decision(decision)
        run = self.store.get_run(payload.run_id)
        task = self.store.get_task(payload.task_id)
        if run and task and decision_value == "require_approval":
            run.status = "blocked"
            task.status = "blocked"
            self.store.save_run(run)
            self.store.save_task(task)
        return decision

    def get_policy_decision(self, decision_id: str) -> PolicyDecision:
        decision = self.store.get_policy_decision(decision_id)
        if decision is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "policy_decision_not_found", "Policy decision was not found.")
        return decision

    def resolve_policy_decision(self, decision_id: str, payload: PolicyDecisionResolutionRequest) -> PolicyDecision:
        decision = self.get_policy_decision(decision_id)
        decision.status = "approved" if payload.resolution == "approved" else "denied"
        decision.resolved_at = utc_now()
        decision.resolved_by = payload.resolved_by
        decision.comment = payload.comment
        self.store.save_policy_decision(decision)

        run = self.store.get_run(decision.run_id)
        task = self.store.get_task(decision.task_id)
        if run and task and run.status == "blocked":
            run.status = "running" if decision.status == "approved" else "failed"
            task.status = "running" if decision.status == "approved" else "failed"
            self.store.save_run(run)
            self.store.save_task(task)
        return decision

    def complete_run(self, run_id: str, payload: CompleteRunRequest, instance: CodexInstance) -> OperationStatusResponse:
        run = self._get_run_owned_by_instance(run_id, instance.instance_id)
        task = self._get_single_task_for_run(run.run_id)
        run.status = payload.status
        run.ended_at = payload.ended_at
        run.summary = payload.summary
        task.status = payload.status
        task.ended_at = payload.ended_at
        self.store.save_run(run)
        self.store.save_task(task)
        self._build_run_fingerprint(run, task)
        return OperationStatusResponse(status=run.status)

    def get_task(self, task_id: str) -> RunTask:
        return self._get_task(task_id)

    def get_run_detail(self, run_id: str, instance: CodexInstance | None = None) -> DashboardRunDetail:
        run = self.store.get_run(run_id)
        if run is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "run_not_found", "Run was not found.")
        if instance is not None and run.instance_id != instance.instance_id:
            raise ApiError(status.HTTP_404_NOT_FOUND, "run_not_found", "Run was not found.")
        task = self._get_single_task_for_run(run_id)
        return DashboardRunDetail(
            run=run,
            task=task,
            events=self.store.list_events(run_id),
            tool_executions=self.store.list_tool_executions(run_id),
            policy_decisions=self.store.list_policy_decisions(run_id),
            fingerprint=self.store.get_workflow_fingerprint_for_run(run_id),
            orchestration=self.store.get_orchestration(run.orchestration_id),
            instance=self.store.get_instance(run.instance_id),
        )

    def dashboard_overview(self) -> DashboardOverviewResponse:
        runs = self.store.list_runs()
        decisions = [decision for run in runs for decision in self.store.list_policy_decisions(run.run_id)]
        recent_error_count = 0
        errors_by_category: dict[str, dict[str, object]] = {}
        for run in runs:
            for event in self.store.list_events(run.run_id):
                if event.type != "error.raised":
                    continue
                recent_error_count += 1
                category = self._classify_error_event(event)
                summary = errors_by_category.setdefault(
                    category,
                    {
                        "count": 0,
                        "orchestration_ids": set(),
                        "last_seen_at": event.timestamp,
                    },
                )
                summary["count"] = int(summary["count"]) + 1
                cast_orchestrations = summary["orchestration_ids"]
                if isinstance(cast_orchestrations, set):
                    cast_orchestrations.add(run.orchestration_id)
                last_seen_at = summary["last_seen_at"]
                if isinstance(last_seen_at, datetime) and event.timestamp > last_seen_at:
                    summary["last_seen_at"] = event.timestamp
        top_workflows = [
            DashboardWorkflowSummary(
                fingerprint_id=fingerprint.fingerprint_id,
                orchestration_id=fingerprint.orchestration_id,
                title_pattern=fingerprint.title_pattern,
                occurrence_count=fingerprint.occurrence_count,
                terminal_status=fingerprint.terminal_status,
                error_categories=fingerprint.error_categories,
                last_seen_at=fingerprint.last_seen_at,
            )
            for fingerprint in self.store.list_workflow_fingerprints()[:5]
        ]
        error_breakdown = sorted(
            (
                DashboardErrorSummary(
                    category=category,
                    occurrence_count=int(summary["count"]),
                    affected_orchestration_ids=sorted(summary["orchestration_ids"]),
                    last_seen_at=summary["last_seen_at"],
                )
                for category, summary in errors_by_category.items()
            ),
            key=lambda item: (-item.occurrence_count, -item.last_seen_at.timestamp(), item.category),
        )[:5]
        return DashboardOverviewResponse(
            orchestration_count=len(self.store.list_orchestrations()),
            active_instance_count=len(self.store.list_instances()),
            running_run_count=sum(1 for run in runs if run.status == "running"),
            blocked_run_count=sum(1 for run in runs if run.status == "blocked"),
            recent_error_count=recent_error_count,
            pending_policy_decision_count=sum(1 for decision in decisions if decision.status == "pending"),
            top_workflows=top_workflows,
            error_breakdown=error_breakdown,
        )

    def list_dashboard_runs(self) -> list[Run]:
        return self.store.list_runs()

    def list_dashboard_instances(self) -> list[CodexInstance]:
        return self.store.list_instances()

    def list_dashboard_orchestrations(self) -> list[Orchestration]:
        return self.store.list_orchestrations()

    def _get_run_owned_by_instance(self, run_id: str, instance_id: str) -> Run:
        run = self.store.get_run(run_id)
        if run is None or run.instance_id != instance_id:
            raise ApiError(status.HTTP_404_NOT_FOUND, "run_not_found", "Run was not found.")
        return run

    def _get_task(self, task_id: str) -> RunTask:
        task = self.store.get_task(task_id)
        if task is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "task_not_found", "Task was not found.")
        return task

    def _get_single_task_for_run(self, run_id: str) -> RunTask:
        for candidate in self.store.list_tasks():
            if candidate.run_id == run_id:
                return candidate
        raise ApiError(status.HTTP_404_NOT_FOUND, "task_not_found", "Task was not found for run.")

    def _record_tool_called(self, event: RunEvent) -> None:
        tool_name = str(event.payload.get("tool_name", "unknown"))
        execution = ToolExecution(
            tool_execution_id=f"tex_{event.event_id.split('_', 1)[1]}",
            run_id=event.run_id,
            task_id=event.task_id,
            tool_name=tool_name,
            status="called",
            started_at=event.timestamp,
            ended_at=None,
            input_summary=event.payload.get("input_summary") if isinstance(event.payload.get("input_summary"), str) else None,
            output_summary=None,
            error_summary=None,
        )
        self.store.save_tool_execution(execution)

    def _record_tool_completed(self, event: RunEvent) -> None:
        tool_name = str(event.payload.get("tool_name", "unknown"))
        executions = [execution for execution in self.store.list_tool_executions(event.run_id) if execution.tool_name == tool_name]
        if executions:
            execution = executions[-1]
            execution.status = "completed"
            execution.ended_at = event.timestamp
            output_summary = event.payload.get("output_summary")
            if isinstance(output_summary, str):
                execution.output_summary = output_summary
        else:
            execution = ToolExecution(
                tool_execution_id=f"tex_{event.event_id.split('_', 1)[1]}",
                run_id=event.run_id,
                task_id=event.task_id,
                tool_name=tool_name,
                status="completed",
                started_at=event.timestamp,
                ended_at=event.timestamp,
                input_summary=None,
                output_summary=event.payload.get("output_summary") if isinstance(event.payload.get("output_summary"), str) else None,
                error_summary=None,
            )
        self.store.save_tool_execution(execution)

    def _evaluate_sensitive_action(self, payload: PreauthorizeActionRequest) -> str:
        if payload.action_type == "write_outside_workspace":
            return "allow" if payload.target.startswith(payload.workspace_path) else "require_approval"
        if payload.action_type in {
            "mass_delete_or_move",
            "destructive_shell",
            "git_push",
            "outbound_network",
            "unapproved_dependency_or_binary",
        }:
            return "require_approval"
        return "deny"

    def _decision_reason(self, action_type: str, decision: str) -> str:
        if decision == "allow":
            return f"Action '{action_type}' is allowed by the local policy profile."
        if decision == "deny":
            return f"Action '{action_type}' is denied by the local policy profile."
        return f"Action '{action_type}' requires operator approval in V1."

    def _build_run_fingerprint(self, run: Run, task: RunTask) -> WorkflowFingerprint:
        events = self.store.list_events(run.run_id)
        tools = self.store.list_tool_executions(run.run_id)
        step_signature = [event.type for event in events]
        tool_signature = [tool.tool_name for tool in tools]
        error_categories = sorted(
            {
                self._classify_error_event(event)
                for event in events
                if event.type == "error.raised"
            }
        )
        key_payload = {
            "orchestration_id": run.orchestration_id,
            "step_signature": step_signature,
            "tool_signature": tool_signature,
            "terminal_status": run.status,
            "error_categories": error_categories,
        }
        fingerprint_key = hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode("utf-8")).hexdigest()
        fingerprint = WorkflowFingerprint(
            fingerprint_id=new_public_id("wfp"),
            title_pattern=task.title,
            orchestration_id=run.orchestration_id,
            step_signature=step_signature,
            tool_signature=tool_signature,
            occurrence_count=1,
            last_seen_at=run.ended_at or utc_now(),
            terminal_status=run.status,
            error_categories=error_categories,
        )
        fingerprint = self.store.upsert_workflow_fingerprint(fingerprint_key, fingerprint)
        self.store.attach_run_fingerprint(run.run_id, fingerprint.fingerprint_id)
        return fingerprint

    def _classify_error_event(self, event: RunEvent) -> str:
        for key in ("error_category", "category", "code"):
            value = event.payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "uncategorized"
