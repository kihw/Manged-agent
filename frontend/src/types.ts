export type RunStatus = "pending" | "running" | "blocked" | "completed" | "failed";

export interface ExecutiveMetrics {
  active_runs: number;
  blocked_runs: number;
  pending_approvals: number;
  recent_errors: number;
  connected_agents: number;
}

export interface RuntimeInfo {
  local_instance_id: string;
  local_instance_workspace_path: string;
  admin_auth_required: boolean;
  app_mode: "local" | "lan";
  poll_interval_seconds: number;
}

export interface ProjectSummary {
  project_id: string;
  display_name: string;
  workspace_path: string;
  run_count: number;
  active_run_count: number;
  blocked_run_count: number;
  pending_approval_count: number;
  recent_error_count: number;
}

export interface RunItem {
  run_id: string;
  task_id: string;
  project_id: string;
  project_name: string;
  orchestration_id: string;
  orchestration_name: string;
  title: string;
  goal: string;
  status: RunStatus;
  current_step: string | null;
  summary: string | null;
  started_at: string;
  ended_at: string | null;
  workspace_path: string;
  has_pending_approval: boolean;
  error_categories: string[];
  workflow_fingerprint_id: string | null;
}

export interface ApprovalItem {
  decision_id: string;
  run_id: string;
  task_id: string;
  project_id: string;
  project_name: string;
  title: string;
  action_type: string;
  reason: string;
  requested_at: string;
}

export interface ErrorItem {
  category: string;
  run_id: string;
  project_id: string;
  project_name: string;
  title: string;
  message: string | null;
  last_seen_at: string;
}

export interface CommandCenterResponse {
  executive: ExecutiveMetrics;
  runtime: RuntimeInfo;
  projects: ProjectSummary[];
  queues: {
    in_progress: RunItem[];
    blocked: RunItem[];
    needs_attention: RunItem[];
    recent: RunItem[];
  };
  urgent: {
    approvals: ApprovalItem[];
    blocked_runs: RunItem[];
    errors: ErrorItem[];
  };
  available_orchestrations: Array<{
    orchestration_id: string;
    name: string;
    version: string;
    status: string;
    entrypoint: string;
    policy_profile: string;
    required_tools: string[];
    required_skills: string[];
    compatibility: string[];
    published_at: string | null;
  }>;
}

export interface RunDetail {
  run: {
    run_id: string;
    orchestration_id: string;
    orchestration_version: string;
    instance_id: string;
    status: RunStatus;
    started_at: string;
    ended_at: string | null;
    trigger: string;
    workspace_path: string;
    summary: string | null;
  };
  task: {
    task_id: string;
    run_id: string;
    title: string;
    goal: string;
    status: RunStatus;
    current_step: string | null;
    started_at: string;
    ended_at: string | null;
  };
  events: Array<{
    event_id: string;
    type: string;
    source: string;
    timestamp: string;
    payload: Record<string, unknown>;
  }>;
  tool_executions: Array<{
    tool_execution_id: string;
    tool_name: string;
    status: string;
    started_at: string;
    ended_at: string | null;
    input_summary: string | null;
    output_summary: string | null;
    error_summary: string | null;
  }>;
  policy_decisions: Array<{
    decision_id: string;
    action_type: string;
    decision: string;
    reason: string;
    status: string;
    requested_at: string;
    resolved_at: string | null;
    comment: string | null;
  }>;
  fingerprint: {
    fingerprint_id: string;
    title_pattern: string;
    error_categories: string[];
  } | null;
  orchestration: {
    orchestration_id: string;
    name: string;
  } | null;
  instance: {
    instance_id: string;
    machine_id: string;
    client_kind: string;
  } | null;
}

export interface LaunchRunPayload {
  orchestration_id: string;
  title: string;
  goal: string;
  workspace_path: string;
  trigger: string;
}

export interface RelaunchRunPayload {
  title?: string;
  goal?: string;
  workspace_path?: string;
  trigger?: string;
}
