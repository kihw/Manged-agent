CREATE TABLE IF NOT EXISTS orchestrations (
    orchestration_id TEXT PRIMARY KEY,
    current_version TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    policy_profile TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    orchestration_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orchestration_versions (
    orchestration_id TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    orchestration_json TEXT NOT NULL,
    PRIMARY KEY (orchestration_id, version)
);

CREATE TABLE IF NOT EXISTS codex_instances (
    instance_id TEXT PRIMARY KEY,
    instance_token TEXT NOT NULL UNIQUE,
    machine_id TEXT NOT NULL,
    client_kind TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    instance_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    orchestration_id TEXT NOT NULL,
    orchestration_version TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    trigger TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    summary TEXT,
    run_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    task_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_executions (
    tool_execution_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    tool_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_decisions (
    decision_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    decision_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_fingerprints (
    fingerprint_id TEXT PRIMARY KEY,
    fingerprint_key TEXT NOT NULL UNIQUE,
    orchestration_id TEXT NOT NULL,
    title_pattern TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    terminal_status TEXT NOT NULL,
    fingerprint_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_fingerprints (
    run_id TEXT PRIMARY KEY,
    fingerprint_id TEXT NOT NULL
);
