from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Protocol

from app.models import (
    CodexInstance,
    Orchestration,
    PolicyDecision,
    Run,
    RunEvent,
    RunTask,
    ToolExecution,
    WorkflowFingerprint,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS orchestrations (
    orchestration_id TEXT PRIMARY KEY,
    current_version TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    policy_profile TEXT NOT NULL,
    published_at TEXT,
    orchestration_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orchestration_versions (
    orchestration_id TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TEXT NOT NULL,
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
    registered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    instance_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    orchestration_id TEXT NOT NULL,
    orchestration_version TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
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
    started_at TEXT NOT NULL,
    ended_at TEXT,
    task_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_executions (
    tool_execution_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    tool_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policy_decisions (
    decision_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decision_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_fingerprints (
    fingerprint_id TEXT PRIMARY KEY,
    fingerprint_key TEXT NOT NULL UNIQUE,
    orchestration_id TEXT NOT NULL,
    title_pattern TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL,
    last_seen_at TEXT NOT NULL,
    terminal_status TEXT NOT NULL,
    fingerprint_json TEXT NOT NULL
);
"""


POSTGRES_SCHEMA = """
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
"""


def _dump(model) -> str:
    return model.model_dump_json()


def _load(model_cls, payload: str):
    return model_cls.model_validate_json(payload)


class PlatformStore(Protocol):
    def save_orchestration(self, orchestration: Orchestration) -> Orchestration: ...
    def get_orchestration(self, orchestration_id: str) -> Orchestration | None: ...
    def list_orchestrations(self) -> list[Orchestration]: ...
    def save_instance(self, instance: CodexInstance) -> CodexInstance: ...
    def get_instance_by_token(self, instance_token: str) -> CodexInstance | None: ...
    def get_instance(self, instance_id: str) -> CodexInstance | None: ...
    def list_instances(self) -> list[CodexInstance]: ...
    def save_run(self, run: Run) -> Run: ...
    def get_run(self, run_id: str) -> Run | None: ...
    def list_runs(self) -> list[Run]: ...
    def save_task(self, task: RunTask) -> RunTask: ...
    def get_task(self, task_id: str) -> RunTask | None: ...
    def list_tasks(self) -> list[RunTask]: ...
    def save_event(self, event: RunEvent) -> None: ...
    def list_events(self, run_id: str) -> list[RunEvent]: ...
    def save_tool_execution(self, execution: ToolExecution) -> ToolExecution: ...
    def list_tool_executions(self, run_id: str) -> list[ToolExecution]: ...
    def save_policy_decision(self, decision: PolicyDecision) -> PolicyDecision: ...
    def get_policy_decision(self, decision_id: str) -> PolicyDecision | None: ...
    def list_policy_decisions(self, run_id: str) -> list[PolicyDecision]: ...
    def upsert_workflow_fingerprint(self, fingerprint_key: str, fingerprint: WorkflowFingerprint) -> WorkflowFingerprint: ...
    def get_workflow_fingerprint_by_key(self, fingerprint_key: str) -> WorkflowFingerprint | None: ...
    def list_workflow_fingerprints(self) -> list[WorkflowFingerprint]: ...
    def get_workflow_fingerprint_for_run(self, run_id: str) -> WorkflowFingerprint | None: ...
    def attach_run_fingerprint(self, run_id: str, fingerprint_id: str) -> None: ...
    def list_run_ids_for_fingerprint(self, fingerprint_id: str) -> list[str]: ...


class SQLitePlatformStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(SQLITE_SCHEMA)
            connection.execute("CREATE TABLE IF NOT EXISTS run_fingerprints (run_id TEXT PRIMARY KEY, fingerprint_id TEXT NOT NULL)")

    def save_orchestration(self, orchestration: Orchestration) -> Orchestration:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO orchestrations (
                    orchestration_id, current_version, name, status, entrypoint, policy_profile, published_at, orchestration_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(orchestration_id) DO UPDATE SET
                    current_version = excluded.current_version,
                    name = excluded.name,
                    status = excluded.status,
                    entrypoint = excluded.entrypoint,
                    policy_profile = excluded.policy_profile,
                    published_at = excluded.published_at,
                    orchestration_json = excluded.orchestration_json
                """,
                (
                    orchestration.orchestration_id,
                    orchestration.version,
                    orchestration.name,
                    orchestration.status,
                    orchestration.entrypoint,
                    orchestration.policy_profile,
                    orchestration.published_at.isoformat() if orchestration.published_at else None,
                    _dump(orchestration),
                ),
            )
            connection.execute(
                """
                INSERT INTO orchestration_versions (orchestration_id, version, created_at, orchestration_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(orchestration_id, version) DO UPDATE SET orchestration_json = excluded.orchestration_json
                """,
                (orchestration.orchestration_id, orchestration.version, utc_now().isoformat(), _dump(orchestration)),
            )
        return orchestration

    def get_orchestration(self, orchestration_id: str) -> Orchestration | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT orchestration_json FROM orchestrations WHERE orchestration_id = ?",
                (orchestration_id,),
            ).fetchone()
        return _load(Orchestration, row["orchestration_json"]) if row else None

    def list_orchestrations(self) -> list[Orchestration]:
        with self._connect() as connection:
            rows = connection.execute("SELECT orchestration_json FROM orchestrations ORDER BY name ASC").fetchall()
        return [_load(Orchestration, row["orchestration_json"]) for row in rows]

    def save_instance(self, instance: CodexInstance) -> CodexInstance:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO codex_instances (
                    instance_id, instance_token, machine_id, client_kind, workspace_path, capabilities_json,
                    registered_at, last_seen_at, instance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    instance_token = excluded.instance_token,
                    machine_id = excluded.machine_id,
                    client_kind = excluded.client_kind,
                    workspace_path = excluded.workspace_path,
                    capabilities_json = excluded.capabilities_json,
                    registered_at = excluded.registered_at,
                    last_seen_at = excluded.last_seen_at,
                    instance_json = excluded.instance_json
                """,
                (
                    instance.instance_id,
                    instance.instance_token,
                    instance.machine_id,
                    instance.client_kind,
                    instance.workspace_path,
                    json.dumps(instance.capabilities),
                    instance.registered_at.isoformat(),
                    instance.last_seen_at.isoformat(),
                    _dump(instance),
                ),
            )
        return instance

    def get_instance_by_token(self, instance_token: str) -> CodexInstance | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT instance_json FROM codex_instances WHERE instance_token = ?",
                (instance_token,),
            ).fetchone()
        return _load(CodexInstance, row["instance_json"]) if row else None

    def get_instance(self, instance_id: str) -> CodexInstance | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT instance_json FROM codex_instances WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
        return _load(CodexInstance, row["instance_json"]) if row else None

    def list_instances(self) -> list[CodexInstance]:
        with self._connect() as connection:
            rows = connection.execute("SELECT instance_json FROM codex_instances ORDER BY last_seen_at DESC").fetchall()
        return [_load(CodexInstance, row["instance_json"]) for row in rows]

    def save_run(self, run: Run) -> Run:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, orchestration_id, orchestration_version, instance_id, status, started_at, ended_at,
                    trigger, workspace_path, summary, run_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    ended_at = excluded.ended_at,
                    summary = excluded.summary,
                    run_json = excluded.run_json
                """,
                (
                    run.run_id,
                    run.orchestration_id,
                    run.orchestration_version,
                    run.instance_id,
                    run.status,
                    run.started_at.isoformat(),
                    run.ended_at.isoformat() if run.ended_at else None,
                    run.trigger,
                    run.workspace_path,
                    run.summary,
                    _dump(run),
                ),
            )
        return run

    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as connection:
            row = connection.execute("SELECT run_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _load(Run, row["run_json"]) if row else None

    def list_runs(self) -> list[Run]:
        with self._connect() as connection:
            rows = connection.execute("SELECT run_json FROM runs ORDER BY started_at DESC").fetchall()
        return [_load(Run, row["run_json"]) for row in rows]

    def save_task(self, task: RunTask) -> RunTask:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (task_id, run_id, title, goal, status, current_step, started_at, ended_at, task_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    title = excluded.title,
                    goal = excluded.goal,
                    status = excluded.status,
                    current_step = excluded.current_step,
                    ended_at = excluded.ended_at,
                    task_json = excluded.task_json
                """,
                (
                    task.task_id,
                    task.run_id,
                    task.title,
                    task.goal,
                    task.status,
                    task.current_step,
                    task.started_at.isoformat(),
                    task.ended_at.isoformat() if task.ended_at else None,
                    _dump(task),
                ),
            )
        return task

    def get_task(self, task_id: str) -> RunTask | None:
        with self._connect() as connection:
            row = connection.execute("SELECT task_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return _load(RunTask, row["task_json"]) if row else None

    def list_tasks(self) -> list[RunTask]:
        with self._connect() as connection:
            rows = connection.execute("SELECT task_json FROM tasks ORDER BY started_at DESC").fetchall()
        return [_load(RunTask, row["task_json"]) for row in rows]

    def save_event(self, event: RunEvent) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_events (event_id, run_id, task_id, event_type, source, timestamp, event_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET event_json = excluded.event_json
                """,
                (
                    event.event_id,
                    event.run_id,
                    event.task_id,
                    event.type,
                    event.source,
                    event.timestamp.isoformat(),
                    _dump(event),
                ),
            )

    def list_events(self, run_id: str) -> list[RunEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_json FROM run_events WHERE run_id = ? ORDER BY timestamp ASC",
                (run_id,),
            ).fetchall()
        return [_load(RunEvent, row["event_json"]) for row in rows]

    def save_tool_execution(self, execution: ToolExecution) -> ToolExecution:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_executions (
                    tool_execution_id, run_id, task_id, tool_name, status, started_at, ended_at, tool_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tool_execution_id) DO UPDATE SET
                    status = excluded.status,
                    ended_at = excluded.ended_at,
                    tool_json = excluded.tool_json
                """,
                (
                    execution.tool_execution_id,
                    execution.run_id,
                    execution.task_id,
                    execution.tool_name,
                    execution.status,
                    execution.started_at.isoformat(),
                    execution.ended_at.isoformat() if execution.ended_at else None,
                    _dump(execution),
                ),
            )
        return execution

    def list_tool_executions(self, run_id: str) -> list[ToolExecution]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT tool_json FROM tool_executions WHERE run_id = ? ORDER BY started_at ASC",
                (run_id,),
            ).fetchall()
        return [_load(ToolExecution, row["tool_json"]) for row in rows]

    def save_policy_decision(self, decision: PolicyDecision) -> PolicyDecision:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO policy_decisions (
                    decision_id, run_id, task_id, action_type, status, requested_at, decision_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    status = excluded.status,
                    decision_json = excluded.decision_json
                """,
                (
                    decision.decision_id,
                    decision.run_id,
                    decision.task_id,
                    decision.action_type,
                    decision.status,
                    decision.requested_at.isoformat(),
                    _dump(decision),
                ),
            )
        return decision

    def get_policy_decision(self, decision_id: str) -> PolicyDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT decision_json FROM policy_decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
        return _load(PolicyDecision, row["decision_json"]) if row else None

    def list_policy_decisions(self, run_id: str) -> list[PolicyDecision]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT decision_json FROM policy_decisions WHERE run_id = ? ORDER BY requested_at ASC",
                (run_id,),
            ).fetchall()
        return [_load(PolicyDecision, row["decision_json"]) for row in rows]

    def upsert_workflow_fingerprint(self, fingerprint_key: str, fingerprint: WorkflowFingerprint) -> WorkflowFingerprint:
        existing = self.get_workflow_fingerprint_by_key(fingerprint_key)
        if existing is not None:
            fingerprint = WorkflowFingerprint(
                **{
                    **fingerprint.model_dump(),
                    "fingerprint_id": existing.fingerprint_id,
                    "occurrence_count": existing.occurrence_count + 1,
                }
            )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_fingerprints (
                    fingerprint_id, fingerprint_key, orchestration_id, title_pattern, occurrence_count,
                    last_seen_at, terminal_status, fingerprint_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint_key) DO UPDATE SET
                    occurrence_count = excluded.occurrence_count,
                    last_seen_at = excluded.last_seen_at,
                    terminal_status = excluded.terminal_status,
                    fingerprint_json = excluded.fingerprint_json
                """,
                (
                    fingerprint.fingerprint_id,
                    fingerprint_key,
                    fingerprint.orchestration_id,
                    fingerprint.title_pattern,
                    fingerprint.occurrence_count,
                    fingerprint.last_seen_at.isoformat(),
                    fingerprint.terminal_status,
                    _dump(fingerprint),
                ),
            )
        return fingerprint

    def get_workflow_fingerprint_by_key(self, fingerprint_key: str) -> WorkflowFingerprint | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT fingerprint_json FROM workflow_fingerprints WHERE fingerprint_key = ?",
                (fingerprint_key,),
            ).fetchone()
        return _load(WorkflowFingerprint, row["fingerprint_json"]) if row else None

    def list_workflow_fingerprints(self) -> list[WorkflowFingerprint]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT fingerprint_json
                FROM workflow_fingerprints
                ORDER BY occurrence_count DESC, last_seen_at DESC
                """
            ).fetchall()
        return [_load(WorkflowFingerprint, row["fingerprint_json"]) for row in rows]

    def attach_run_fingerprint(self, run_id: str, fingerprint_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_fingerprints (run_id, fingerprint_id) VALUES (?, ?)
                ON CONFLICT(run_id) DO UPDATE SET fingerprint_id = excluded.fingerprint_id
                """,
                (run_id, fingerprint_id),
            )

    def get_workflow_fingerprint_for_run(self, run_id: str) -> WorkflowFingerprint | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT workflow_fingerprints.fingerprint_json
                FROM run_fingerprints
                JOIN workflow_fingerprints ON workflow_fingerprints.fingerprint_id = run_fingerprints.fingerprint_id
                WHERE run_fingerprints.run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return _load(WorkflowFingerprint, row["fingerprint_json"]) if row else None

    def list_run_ids_for_fingerprint(self, fingerprint_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id
                FROM run_fingerprints
                WHERE fingerprint_id = ?
                ORDER BY run_id DESC
                """,
                (fingerprint_id,),
            ).fetchall()
        return [str(row["run_id"]) for row in rows]


class PostgresPlatformStore(SQLitePlatformStore):
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._ensure_schema()

    @contextmanager
    def _pg_connection(self):
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            yield _PostgresCompatConnection(connection)

    def _connect(self):
        return self._pg_connection()

    def _ensure_schema(self) -> None:
        with self._pg_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_SCHEMA)
                cursor.execute("CREATE TABLE IF NOT EXISTS run_fingerprints (run_id TEXT PRIMARY KEY, fingerprint_id TEXT NOT NULL)")
            connection.commit()


class _PostgresCompatConnection:
    def __init__(self, connection) -> None:
        self.connection = connection

    def execute(self, query: str, params: tuple | None = None):
        return self.connection.execute(query.replace("?", "%s"), params or ())

    def cursor(self):
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()

    def executescript(self, query: str) -> None:
        self.connection.execute(query)
