import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const commandCenterPayload = {
  executive: {
    active_runs: 2,
    blocked_runs: 1,
    pending_approvals: 1,
    recent_errors: 1,
    connected_agents: 2,
  },
  runtime: {
    local_instance_id: "inst_command01",
    local_instance_workspace_path: "D:/Managed Agent",
    admin_auth_required: false,
    app_mode: "local",
    poll_interval_seconds: 5,
  },
  projects: [
    {
      project_id: "prj_atlas",
      display_name: "Atlas",
      workspace_path: "D:/Projects/Atlas",
      run_count: 2,
      active_run_count: 1,
      blocked_run_count: 1,
      pending_approval_count: 1,
      recent_error_count: 0,
    },
  ],
  queues: {
    in_progress: [
      {
        run_id: "run_active001",
        task_id: "task_active001",
        project_id: "prj_atlas",
        project_name: "Atlas",
        orchestration_id: "orc_atlas_sync",
        orchestration_name: "Atlas Sync",
        title: "Atlas running",
        goal: "Keep Atlas healthy",
        status: "running",
        current_step: "sync",
        summary: null,
        started_at: "2026-04-09T18:00:00Z",
        ended_at: null,
        workspace_path: "D:/Projects/Atlas",
        has_pending_approval: false,
        error_categories: [],
        workflow_fingerprint_id: null,
      },
    ],
    blocked: [
      {
        run_id: "run_blocked001",
        task_id: "task_blocked001",
        project_id: "prj_atlas",
        project_name: "Atlas",
        orchestration_id: "orc_atlas_sync",
        orchestration_name: "Atlas Sync",
        title: "Atlas blocked",
        goal: "Needs approval",
        status: "blocked",
        current_step: "ship",
        summary: null,
        started_at: "2026-04-09T18:10:00Z",
        ended_at: null,
        workspace_path: "D:/Projects/Atlas",
        has_pending_approval: true,
        error_categories: [],
        workflow_fingerprint_id: null,
      },
    ],
    needs_attention: [],
    recent: [],
  },
  urgent: {
    approvals: [
      {
        decision_id: "dec_pending01",
        run_id: "run_blocked001",
        task_id: "task_blocked001",
        project_id: "prj_atlas",
        project_name: "Atlas",
        title: "Atlas blocked",
        action_type: "outbound_network",
        reason: "Action requires operator approval in V1.",
        requested_at: "2026-04-09T18:12:00Z",
      },
    ],
    blocked_runs: [],
    errors: [],
  },
  available_orchestrations: [
    {
      orchestration_id: "orc_atlas_sync",
      name: "Atlas Sync",
      version: "1.0.0",
      status: "published",
      entrypoint: "codex://orchestrations/orc_atlas_sync",
      policy_profile: "default",
      required_tools: ["shell"],
      required_skills: [],
      compatibility: ["windows_app"],
      published_at: "2026-04-09T18:00:00Z",
    },
  ],
};

const runDetailPayload = {
  run: {
    run_id: "run_active001",
    orchestration_id: "orc_atlas_sync",
    orchestration_version: "1.0.0",
    instance_id: "inst_command01",
    status: "running",
    started_at: "2026-04-09T18:00:00Z",
    ended_at: null,
    trigger: "manual-ui",
    workspace_path: "D:/Projects/Atlas",
    summary: null,
  },
  task: {
    task_id: "task_active001",
    run_id: "run_active001",
    title: "Atlas running",
    goal: "Keep Atlas healthy",
    status: "running",
    current_step: "sync",
    started_at: "2026-04-09T18:00:00Z",
    ended_at: null,
  },
  events: [
    {
      event_id: "evt_one",
      source: "codex",
      type: "run.started",
      timestamp: "2026-04-09T18:00:00Z",
      payload: { task_title: "Atlas running" },
    },
  ],
  tool_executions: [],
  policy_decisions: [],
  fingerprint: null,
  orchestration: {
    orchestration_id: "orc_atlas_sync",
    name: "Atlas Sync",
  },
  instance: {
    instance_id: "inst_command01",
    machine_id: "managed-agent",
    client_kind: "windows_app",
  },
};

function renderApp() {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/v1/dashboard/command-center")) {
          return Promise.resolve(new Response(JSON.stringify(commandCenterPayload), { status: 200 }));
        }
        if (url.endsWith("/v1/dashboard/runs/run_active001")) {
          return Promise.resolve(new Response(JSON.stringify(runDetailPayload), { status: 200 }));
        }
        if (url.endsWith("/v1/dashboard/runs/launch")) {
          return Promise.resolve(new Response(JSON.stringify({ run_id: "run_new001", task_id: "task_new001" }), { status: 201 }));
        }
        if (url.endsWith("/v1/policy-decisions/dec_pending01/resolve") && init?.method === "POST") {
          return Promise.resolve(new Response(JSON.stringify({ status: "approved" }), { status: 200 }));
        }
        if (url.endsWith("/v1/dashboard/runs/run_active001/relaunch") && init?.method === "POST") {
          return Promise.resolve(new Response(JSON.stringify({ run_id: "run_new002", task_id: "task_new002" }), { status: 201 }));
        }
        return Promise.resolve(new Response("not found", { status: 404 }));
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders cockpit data and opens the run drawer with investigation", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderApp();

    await screen.findByText("Command Center");
    expect(screen.getByText("Atlas running")).toBeInTheDocument();
    expect(screen.getByText("Runs actifs")).toBeInTheDocument();

    await user.click(screen.getByText("Atlas running"));

    const dialog = await screen.findByRole("dialog", { name: "Atlas running" });
    expect(within(dialog).getByText("Atlas Sync")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Investiguer" }));

    await waitFor(() => {
      expect(screen.getByText("Profondeur technique")).toBeInTheDocument();
      expect(screen.getByText("run.started")).toBeInTheDocument();
    });
  });

  it("submits launch and approval actions", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const fetchSpy = global.fetch as ReturnType<typeof vi.fn>;
    renderApp();

    await screen.findByText("Command Center");
    await user.click(await screen.findByRole("button", { name: "Nouvelle tâche" }));

    await user.type(screen.getByLabelText("Titre"), "Launched from UI");
    await user.type(screen.getByLabelText("Objectif"), "Run from command center");
    await user.click(screen.getByRole("button", { name: "Lancer" }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/v1/dashboard/runs/launch",
        expect.objectContaining({ method: "POST" })
      );
    });

    const approvalButton = screen
      .getAllByRole("button", { name: /Atlas blocked/i })
      .find((element) => element.className.includes("urgent-card"));
    expect(approvalButton).toBeDefined();
    await user.click(approvalButton!);
    await user.click(screen.getByRole("button", { name: "Approuver" }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/v1/policy-decisions/dec_pending01/resolve",
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});
