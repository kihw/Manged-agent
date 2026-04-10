from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import PureWindowsPath

from fastapi import status

from app.models import (
    BatchRunEventsRequest,
    CommandCenterApprovalItem,
    CommandCenterErrorItem,
    CommandCenterExecutiveMetrics,
    CommandCenterProject,
    CommandCenterQueues,
    CommandCenterRunItem,
    CommandCenterRuntimeInfo,
    CommandCenterUrgentItems,
    CodexInstance,
    CompleteRunRequest,
    DashboardCommandCenterResponse,
    DashboardErrorDetail,
    DashboardErrorSummary,
    DashboardLaunchRunRequest,
    DashboardOverviewResponse,
    DashboardRelaunchRunRequest,
    DashboardRunDetail,
    DashboardRunSummary,
    DashboardWorkflowDetail,
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
        error_breakdown = self.list_dashboard_errors(limit=5)
        return DashboardOverviewResponse(
            orchestration_count=len(self.store.list_orchestrations()),
            active_instance_count=len(self.store.list_instances()),
            running_run_count=sum(1 for run in runs if run.status == "running"),
            blocked_run_count=sum(1 for run in runs if run.status == "blocked"),
            recent_error_count=sum(item.occurrence_count for item in error_breakdown),
            pending_policy_decision_count=sum(1 for decision in decisions if decision.status == "pending"),
            top_workflows=self.list_dashboard_workflows(limit=5),
            error_breakdown=error_breakdown,
        )

    def list_dashboard_runs(self) -> list[Run]:
        return self.store.list_runs()

    def list_dashboard_instances(self) -> list[CodexInstance]:
        return self.store.list_instances()

    def list_dashboard_orchestrations(self) -> list[Orchestration]:
        return self.store.list_orchestrations()

    def dashboard_command_center(
        self,
        *,
        local_instance: CodexInstance,
        admin_auth_required: bool,
    ) -> DashboardCommandCenterResponse:
        runs = self.store.list_runs()
        run_items = [self._build_command_center_run_item(run) for run in runs]
        approvals = self._list_pending_approval_items()
        errors = self._list_command_center_errors()
        projects = self._build_command_center_projects(run_items, approvals, errors)
        return DashboardCommandCenterResponse(
            executive=CommandCenterExecutiveMetrics(
                active_runs=sum(1 for run in runs if run.status in {"pending", "running"}),
                blocked_runs=sum(1 for run in runs if run.status == "blocked"),
                pending_approvals=len(approvals),
                recent_errors=sum(item.occurrence_count for item in self.list_dashboard_errors(limit=50)),
                connected_agents=len(self.store.list_instances()),
            ),
            runtime=CommandCenterRuntimeInfo(
                local_instance_id=local_instance.instance_id,
                local_instance_workspace_path=local_instance.workspace_path,
                admin_auth_required=admin_auth_required,
                app_mode="lan" if admin_auth_required else "local",
                poll_interval_seconds=5,
            ),
            projects=projects,
            queues=CommandCenterQueues(
                in_progress=[item for item in run_items if item.status in {"pending", "running"}],
                blocked=[item for item in run_items if item.status == "blocked"],
                needs_attention=[item for item in run_items if item.status in {"failed", "blocked"} or item.has_pending_approval or bool(item.error_categories)],
                recent=sorted(
                    [item for item in run_items if item.status in {"completed", "failed"}],
                    key=lambda item: item.ended_at or item.started_at,
                    reverse=True,
                )[:10],
            ),
            urgent=CommandCenterUrgentItems(
                approvals=approvals,
                blocked_runs=[item for item in run_items if item.status == "blocked"],
                errors=errors,
            ),
            available_orchestrations=[
                orchestration
                for orchestration in self.store.list_orchestrations()
                if orchestration.status == "published"
                and (not orchestration.compatibility or local_instance.client_kind in orchestration.compatibility)
            ],
        )

    def launch_run_from_dashboard(self, payload: DashboardLaunchRunRequest, local_instance: CodexInstance) -> StartRunResponse:
        return self.start_run(
            StartRunRequest(
                orchestration_id=payload.orchestration_id,
                instance_id=local_instance.instance_id,
                title=payload.title,
                goal=payload.goal,
                workspace_path=payload.workspace_path,
                trigger=payload.trigger,
            ),
            local_instance,
        )

    def relaunch_run_from_dashboard(
        self,
        run_id: str,
        payload: DashboardRelaunchRunRequest,
        local_instance: CodexInstance,
    ) -> StartRunResponse:
        detail = self.get_run_detail(run_id)
        return self.start_run(
            StartRunRequest(
                orchestration_id=detail.run.orchestration_id,
                instance_id=local_instance.instance_id,
                title=payload.title or detail.task.title,
                goal=payload.goal or detail.task.goal,
                workspace_path=payload.workspace_path or detail.run.workspace_path,
                trigger=payload.trigger or detail.run.trigger,
            ),
            local_instance,
        )

    def list_dashboard_workflows(
        self,
        *,
        orchestration_id: str | None = None,
        terminal_status: str | None = None,
        limit: int = 50,
    ) -> list[DashboardWorkflowSummary]:
        summaries: list[DashboardWorkflowSummary] = []
        for fingerprint in self.store.list_workflow_fingerprints():
            if orchestration_id and fingerprint.orchestration_id != orchestration_id:
                continue
            if terminal_status and fingerprint.terminal_status != terminal_status:
                continue
            latest_run, latest_task = self._get_latest_run_and_task_for_fingerprint(fingerprint.fingerprint_id)
            if latest_run is None or latest_task is None:
                continue
            summaries.append(
                DashboardWorkflowSummary(
                    fingerprint_id=fingerprint.fingerprint_id,
                    orchestration_id=fingerprint.orchestration_id,
                    title_pattern=fingerprint.title_pattern,
                    occurrence_count=fingerprint.occurrence_count,
                    terminal_status=fingerprint.terminal_status,
                    error_categories=fingerprint.error_categories,
                    last_seen_at=fingerprint.last_seen_at,
                    last_run_id=latest_run.run_id,
                    latest_task_title=latest_task.title,
                )
            )
        return summaries[:limit]

    def get_dashboard_workflow_detail(self, fingerprint_id: str, *, limit: int = 10) -> DashboardWorkflowDetail:
        summary = next((item for item in self.list_dashboard_workflows(limit=500) if item.fingerprint_id == fingerprint_id), None)
        if summary is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "workflow_not_found", "Workflow fingerprint was not found.")
        fingerprint = next(
            (item for item in self.store.list_workflow_fingerprints() if item.fingerprint_id == fingerprint_id),
            None,
        )
        if fingerprint is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "workflow_not_found", "Workflow fingerprint was not found.")
        recent_runs = self._list_recent_runs_for_fingerprint(fingerprint_id, limit=limit)
        return DashboardWorkflowDetail(
            workflow=summary,
            recent_runs=recent_runs,
            step_signature=fingerprint.step_signature,
            tool_signature=fingerprint.tool_signature,
        )

    def list_dashboard_errors(
        self,
        *,
        orchestration_id: str | None = None,
        instance_id: str | None = None,
        limit: int = 50,
    ) -> list[DashboardErrorSummary]:
        grouped = self._group_error_occurrences(orchestration_id=orchestration_id, instance_id=instance_id)
        summaries = [
            DashboardErrorSummary(
                category=category,
                occurrence_count=len(items),
                affected_orchestration_ids=sorted({item["run"].orchestration_id for item in items}),
                last_seen_at=items[0]["event"].timestamp,
                last_run_id=items[0]["run"].run_id,
                sample_messages=self._collect_sample_messages(items),
            )
            for category, items in grouped.items()
        ]
        summaries.sort(key=lambda item: (-item.occurrence_count, -item.last_seen_at.timestamp(), item.category))
        return summaries[:limit]

    def get_dashboard_error_detail(
        self,
        category: str,
        *,
        orchestration_id: str | None = None,
        instance_id: str | None = None,
        limit: int = 10,
    ) -> DashboardErrorDetail:
        grouped = self._group_error_occurrences(orchestration_id=orchestration_id, instance_id=instance_id)
        items = grouped.get(category)
        if not items:
            raise ApiError(status.HTTP_404_NOT_FOUND, "error_category_not_found", "Error category was not found.")
        recent_runs = self._dedupe_recent_run_summaries(items, limit=limit)
        return DashboardErrorDetail(
            category=category,
            occurrence_count=len(items),
            affected_orchestration_ids=sorted({item["run"].orchestration_id for item in items}),
            recent_runs=recent_runs,
            sample_messages=self._collect_sample_messages(items),
        )

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

    def _extract_error_message(self, event: RunEvent) -> str | None:
        for key in ("message", "error"):
            value = event.payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _get_latest_run_and_task_for_fingerprint(self, fingerprint_id: str) -> tuple[Run | None, RunTask | None]:
        runs = [
            self.store.get_run(run_id)
            for run_id in self.store.list_run_ids_for_fingerprint(fingerprint_id)
        ]
        valid_runs = [run for run in runs if run is not None]
        valid_runs.sort(key=lambda run: run.started_at, reverse=True)
        if not valid_runs:
            return None, None
        latest_run = valid_runs[0]
        return latest_run, self._get_single_task_for_run(latest_run.run_id)

    def _list_recent_runs_for_fingerprint(self, fingerprint_id: str, *, limit: int) -> list[DashboardRunSummary]:
        run_summaries: list[DashboardRunSummary] = []
        runs = [
            self.store.get_run(run_id)
            for run_id in self.store.list_run_ids_for_fingerprint(fingerprint_id)
        ]
        valid_runs = [run for run in runs if run is not None]
        valid_runs.sort(key=lambda run: run.started_at, reverse=True)
        for run in valid_runs[:limit]:
            run_summaries.append(self._build_run_summary(run))
        return run_summaries

    def _build_run_summary(self, run: Run) -> DashboardRunSummary:
        task = self._get_single_task_for_run(run.run_id)
        return DashboardRunSummary(
            run_id=run.run_id,
            orchestration_id=run.orchestration_id,
            status=run.status,
            started_at=run.started_at,
            ended_at=run.ended_at,
            task_title=task.title,
        )

    def _build_command_center_run_item(self, run: Run) -> CommandCenterRunItem:
        task = self._get_single_task_for_run(run.run_id)
        orchestration = self.store.get_orchestration(run.orchestration_id)
        fingerprint = self.store.get_workflow_fingerprint_for_run(run.run_id)
        pending_approvals = any(decision.status == "pending" for decision in self.store.list_policy_decisions(run.run_id))
        project_id, project_name = self._derive_project_identity(run.workspace_path, orchestration.name if orchestration else run.orchestration_id)
        error_categories = fingerprint.error_categories if fingerprint else [
            self._classify_error_event(event)
            for event in self.store.list_events(run.run_id)
            if event.type == "error.raised"
        ]
        return CommandCenterRunItem(
            run_id=run.run_id,
            task_id=task.task_id,
            project_id=project_id,
            project_name=project_name,
            orchestration_id=run.orchestration_id,
            orchestration_name=orchestration.name if orchestration else run.orchestration_id,
            title=task.title,
            goal=task.goal,
            status=run.status,
            current_step=task.current_step,
            summary=run.summary,
            started_at=run.started_at,
            ended_at=run.ended_at,
            workspace_path=run.workspace_path,
            has_pending_approval=pending_approvals,
            error_categories=sorted(set(error_categories)),
            workflow_fingerprint_id=fingerprint.fingerprint_id if fingerprint else None,
        )

    def _build_command_center_projects(
        self,
        run_items: list[CommandCenterRunItem],
        approvals: list[CommandCenterApprovalItem],
        errors: list[CommandCenterErrorItem],
    ) -> list[CommandCenterProject]:
        project_map: dict[str, CommandCenterProject] = {}
        for item in run_items:
            project = project_map.setdefault(
                item.project_id,
                CommandCenterProject(
                    project_id=item.project_id,
                    display_name=item.project_name,
                    workspace_path=item.workspace_path,
                    run_count=0,
                    active_run_count=0,
                    blocked_run_count=0,
                    pending_approval_count=0,
                    recent_error_count=0,
                ),
            )
            project.run_count += 1
            if item.status in {"pending", "running"}:
                project.active_run_count += 1
            if item.status == "blocked":
                project.blocked_run_count += 1
        for approval in approvals:
            if approval.project_id in project_map:
                project_map[approval.project_id].pending_approval_count += 1
        for error in errors:
            if error.project_id in project_map:
                project_map[error.project_id].recent_error_count += 1
        return sorted(project_map.values(), key=lambda project: (project.display_name.lower(), project.workspace_path.lower()))

    def _list_pending_approval_items(self) -> list[CommandCenterApprovalItem]:
        items: list[CommandCenterApprovalItem] = []
        for run in self.store.list_runs():
            task = self._get_single_task_for_run(run.run_id)
            orchestration = self.store.get_orchestration(run.orchestration_id)
            project_id, project_name = self._derive_project_identity(run.workspace_path, orchestration.name if orchestration else run.orchestration_id)
            for decision in self.store.list_policy_decisions(run.run_id):
                if decision.status != "pending":
                    continue
                items.append(
                    CommandCenterApprovalItem(
                        decision_id=decision.decision_id,
                        run_id=run.run_id,
                        task_id=task.task_id,
                        project_id=project_id,
                        project_name=project_name,
                        title=task.title,
                        action_type=decision.action_type,
                        reason=decision.reason,
                        requested_at=decision.requested_at,
                    )
                )
        items.sort(key=lambda item: item.requested_at, reverse=True)
        return items

    def _list_command_center_errors(self, *, limit: int = 10) -> list[CommandCenterErrorItem]:
        items: list[CommandCenterErrorItem] = []
        grouped = self._group_error_occurrences(orchestration_id=None, instance_id=None)
        for category, occurrences in grouped.items():
            latest = occurrences[0]
            run = latest["run"]
            if not isinstance(run, Run):
                continue
            task = self._get_single_task_for_run(run.run_id)
            orchestration = self.store.get_orchestration(run.orchestration_id)
            project_id, project_name = self._derive_project_identity(run.workspace_path, orchestration.name if orchestration else run.orchestration_id)
            items.append(
                CommandCenterErrorItem(
                    category=category,
                    run_id=run.run_id,
                    project_id=project_id,
                    project_name=project_name,
                    title=task.title,
                    message=latest["message"] if isinstance(latest["message"], str) else None,
                    last_seen_at=latest["event"].timestamp,
                )
            )
        items.sort(key=lambda item: item.last_seen_at, reverse=True)
        return items[:limit]

    def _derive_project_identity(self, workspace_path: str, fallback_name: str) -> tuple[str, str]:
        try:
            display_name = PureWindowsPath(workspace_path).name or fallback_name
        except (TypeError, ValueError):
            display_name = fallback_name
        project_id = f"prj_{hashlib.sha1(workspace_path.lower().encode('utf-8')).hexdigest()[:12]}"
        return project_id, display_name

    def _group_error_occurrences(
        self,
        *,
        orchestration_id: str | None,
        instance_id: str | None,
    ) -> dict[str, list[dict[str, object]]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        runs = self.store.list_runs()
        for run in runs:
            if orchestration_id and run.orchestration_id != orchestration_id:
                continue
            if instance_id and run.instance_id != instance_id:
                continue
            for event in self.store.list_events(run.run_id):
                if event.type != "error.raised":
                    continue
                category = self._classify_error_event(event)
                grouped.setdefault(category, []).append(
                    {
                        "event": event,
                        "run": run,
                        "message": self._extract_error_message(event),
                    }
                )
        for items in grouped.values():
            items.sort(key=lambda item: item["event"].timestamp, reverse=True)
        return grouped

    def _collect_sample_messages(self, items: list[dict[str, object]], *, limit: int = 3) -> list[str]:
        messages: list[str] = []
        for item in items:
            message = item.get("message")
            if isinstance(message, str) and message and message not in messages:
                messages.append(message)
            if len(messages) >= limit:
                break
        return messages

    def _dedupe_recent_run_summaries(self, items: list[dict[str, object]], *, limit: int) -> list[DashboardRunSummary]:
        recent: list[DashboardRunSummary] = []
        seen_run_ids: set[str] = set()
        for item in items:
            run = item.get("run")
            if not isinstance(run, Run) or run.run_id in seen_run_ids:
                continue
            seen_run_ids.add(run.run_id)
            recent.append(self._build_run_summary(run))
            if len(recent) >= limit:
                break
        return recent
