from __future__ import annotations

import argparse
from datetime import UTC, datetime

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Managed Agent V1 smoke test.")
    parser.add_argument("--base-url", default="http://localhost:8080")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        orchestration = client.post(
            "/v1/orchestrations",
            json={
                "orchestration_id": "orc_smoke",
                "name": "Smoke orchestration",
                "version": "1.0.0",
                "status": "published",
                "entrypoint": "codex://orchestrations/smoke",
                "required_tools": ["shell", "http"],
                "required_skills": ["planning"],
                "policy_profile": "default",
                "compatibility": ["cli"],
                "published_at": datetime.now(UTC).isoformat(),
            },
        )
        orchestration.raise_for_status()

        instance = client.post(
            "/v1/instances/register",
            json={
                "client_kind": "cli",
                "workspace_path": "D:/Code/Manged-agent",
                "capabilities": ["shell", "http"],
                "machine_id": "machine_smoke",
            },
        )
        instance.raise_for_status()
        token = instance.json()["instance_token"]
        headers = {"X-Instance-Token": token}

        synced = client.get("/v1/orchestrations/sync", headers=headers)
        synced.raise_for_status()

        run = client.post(
            "/v1/runs",
            headers=headers,
            json={
                "orchestration_id": "orc_smoke",
                "instance_id": instance.json()["instance_id"],
                "title": "Smoke run",
                "goal": "Validate the V1 flow.",
                "workspace_path": "D:/Code/Manged-agent",
                "trigger": "manual",
            },
        )
        run.raise_for_status()
        run_payload = run.json()

        events = client.post(
            f"/v1/runs/{run_payload['run_id']}/events:batch",
            headers=headers,
            json={
                "events": [
                    {
                        "event_id": "evt_smoke0001",
                        "run_id": run_payload["run_id"],
                        "task_id": run_payload["task_id"],
                        "source": "codex",
                        "type": "run.started",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "payload": {"task_title": "Smoke run"},
                    }
                ]
            },
        )
        events.raise_for_status()

        decision = client.post(
            "/v1/policy/preauthorize",
            headers=headers,
            json={
                "run_id": run_payload["run_id"],
                "task_id": run_payload["task_id"],
                "action_type": "outbound_network",
                "target": "https://api.example.dev/packages",
                "workspace_path": "D:/Code/Manged-agent",
                "tool_name": "http",
                "metadata": {"method": "GET"},
            },
        )
        decision.raise_for_status()
        decision_id = decision.json()["decision_id"]

        resolved = client.post(
            f"/v1/policy-decisions/{decision_id}/resolve",
            json={"resolution": "approved", "resolved_by": "smoke-test", "comment": "approved"},
        )
        resolved.raise_for_status()

        completed = client.post(
            f"/v1/runs/{run_payload['run_id']}/complete",
            headers=headers,
            json={
                "status": "completed",
                "summary": "Smoke test completed successfully.",
                "ended_at": datetime.now(UTC).isoformat(),
            },
        )
        completed.raise_for_status()

    print("Managed Agent V1 smoke test completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
