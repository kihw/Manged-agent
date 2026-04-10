import type {
  CommandCenterResponse,
  LaunchRunPayload,
  RelaunchRunPayload,
  RunDetail,
} from "./types";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getCommandCenter(): Promise<CommandCenterResponse> {
  return apiFetch<CommandCenterResponse>("/v1/dashboard/command-center");
}

export function getRunDetail(runId: string): Promise<RunDetail> {
  return apiFetch<RunDetail>(`/v1/dashboard/runs/${runId}`);
}

export function launchRun(payload: LaunchRunPayload): Promise<{ run_id: string; task_id: string }> {
  return apiFetch("/v1/dashboard/runs/launch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function relaunchRun(runId: string, payload: RelaunchRunPayload): Promise<{ run_id: string; task_id: string }> {
  return apiFetch(`/v1/dashboard/runs/${runId}/relaunch`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resolveApproval(decisionId: string, resolution: "approved" | "denied", comment: string): Promise<unknown> {
  return apiFetch(`/v1/policy-decisions/${decisionId}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      resolution,
      resolved_by: "command-center",
      comment: comment || null,
    }),
  });
}
