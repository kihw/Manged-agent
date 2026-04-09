from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AdapterOfflineError(RuntimeError):
    pass


class CodexPlatformAdapter:
    def __init__(
        self,
        *,
        client,
        cache_dir: Path,
        client_kind: str,
        workspace_path: str,
        capabilities: list[str],
        machine_id: str,
    ) -> None:
        self.client = client
        self.cache_dir = cache_dir
        self.client_kind = client_kind
        self.workspace_path = workspace_path
        self.capabilities = capabilities
        self.machine_id = machine_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.instance_file = self.cache_dir / "instance.json"
        self.orchestrations_file = self.cache_dir / "orchestrations-cache.json"
        self.outbox_file = self.cache_dir / "outbox.jsonl"

    def register_instance(self) -> dict[str, Any]:
        response = self._require_client().post(
            "/v1/instances/register",
            json={
                "client_kind": self.client_kind,
                "workspace_path": self.workspace_path,
                "capabilities": self.capabilities,
                "machine_id": self.machine_id,
            },
        )
        payload = self._json_or_raise(response)
        self.instance_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def sync_orchestrations(self) -> dict[str, Any]:
        response = self._require_client().get("/v1/orchestrations/sync", headers=self._headers())
        payload = self._json_or_raise(response)
        self.orchestrations_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def load_cached_orchestrations(self) -> list[dict[str, Any]]:
        if not self.orchestrations_file.exists():
            return []
        payload = json.loads(self.orchestrations_file.read_text(encoding="utf-8"))
        return payload.get("orchestrations", [])

    def start_run(self, *, orchestration_id: str, title: str, goal: str, trigger: str) -> dict[str, Any]:
        if self.client is None:
            raise AdapterOfflineError("Platform is unavailable. Cannot start a new run offline.")
        instance = self._load_instance()
        response = self.client.post(
            "/v1/runs",
            headers=self._headers(),
            json={
                "orchestration_id": orchestration_id,
                "instance_id": instance["instance_id"],
                "title": title,
                "goal": goal,
                "workspace_path": self.workspace_path,
                "trigger": trigger,
            },
        )
        return self._json_or_raise(response)

    def emit_events(self, *, run_id: str, task_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        if self.client is None:
            self._append_outbox({"type": "events", "run_id": run_id, "task_id": task_id, "events": events})
            raise AdapterOfflineError("Platform is unavailable. Event batch stored in outbox.")
        response = self.client.post(
            f"/v1/runs/{run_id}/events:batch",
            headers=self._headers(),
            json={"events": events},
        )
        return self._json_or_raise(response)

    def preauthorize(
        self,
        *,
        run_id: str,
        task_id: str,
        action_type: str,
        target: str,
        tool_name: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if self.client is None:
            raise AdapterOfflineError("Platform is unavailable. Sensitive actions cannot be preauthorized offline.")
        response = self.client.post(
            "/v1/policy/preauthorize",
            headers=self._headers(),
            json={
                "run_id": run_id,
                "task_id": task_id,
                "action_type": action_type,
                "target": target,
                "workspace_path": self.workspace_path,
                "tool_name": tool_name,
                "metadata": metadata,
            },
        )
        return self._json_or_raise(response)

    def complete_run(self, *, run_id: str, status: str, summary: str, ended_at: str) -> dict[str, Any]:
        if self.client is None:
            raise AdapterOfflineError("Platform is unavailable. Cannot complete run offline.")
        response = self.client.post(
            f"/v1/runs/{run_id}/complete",
            headers=self._headers(),
            json={"status": status, "summary": summary, "ended_at": ended_at},
        )
        return self._json_or_raise(response)

    def flush_outbox(self) -> int:
        if self.client is None or not self.outbox_file.exists():
            return 0
        entries = [
            json.loads(line)
            for line in self.outbox_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        sent = 0
        for entry in entries:
            if entry["type"] == "events":
                self.emit_events(run_id=entry["run_id"], task_id=entry["task_id"], events=entry["events"])
                sent += 1
        self.outbox_file.unlink(missing_ok=True)
        return sent

    def _append_outbox(self, payload: dict[str, Any]) -> None:
        with self.outbox_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _load_instance(self) -> dict[str, Any]:
        if not self.instance_file.exists():
            raise AdapterOfflineError("No cached instance registration is available.")
        return json.loads(self.instance_file.read_text(encoding="utf-8"))

    def _headers(self) -> dict[str, str]:
        instance = self._load_instance()
        return {"X-Instance-Token": instance["instance_token"]}

    def _require_client(self):
        if self.client is None:
            raise AdapterOfflineError("Platform is unavailable.")
        return self.client

    def _json_or_raise(self, response) -> dict[str, Any]:
        response.raise_for_status()
        return response.json()
