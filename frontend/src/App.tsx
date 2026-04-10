import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getCommandCenter, getRunDetail, launchRun, relaunchRun, resolveApproval } from "./api";
import { ApprovalModal } from "./components/ApprovalModal";
import { ExecutiveStrip } from "./components/ExecutiveStrip";
import { InvestigationPanel } from "./components/InvestigationPanel";
import { LaunchTaskModal } from "./components/LaunchTaskModal";
import { ProjectRail } from "./components/ProjectRail";
import { RunDrawer } from "./components/RunDrawer";
import { RunWorkspace } from "./components/RunWorkspace";
import { UrgentActionPanel } from "./components/UrgentActionPanel";
import type { ApprovalItem, RunItem } from "./types";

export function App() {
  const queryClient = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedRun, setSelectedRun] = useState<RunItem | null>(null);
  const [selectedApproval, setSelectedApproval] = useState<ApprovalItem | null>(null);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [investigationOpen, setInvestigationOpen] = useState(false);

  const commandCenterQuery = useQuery({
    queryKey: ["command-center"],
    queryFn: getCommandCenter,
    refetchInterval: (query) => query.state.data?.runtime.poll_interval_seconds ? query.state.data.runtime.poll_interval_seconds * 1000 : 5000,
  });

  const runDetailQuery = useQuery({
    queryKey: ["run-detail", selectedRun?.run_id],
    queryFn: () => getRunDetail(selectedRun!.run_id),
    enabled: Boolean(selectedRun?.run_id),
  });

  const launchMutation = useMutation({
    mutationFn: launchRun,
    onSuccess: async () => {
      setLaunchOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["command-center"] });
    },
  });

  const relaunchMutation = useMutation({
    mutationFn: (runId: string) => relaunchRun(runId, { trigger: "rerun-ui" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["command-center"] });
    },
  });

  const approvalMutation = useMutation({
    mutationFn: ({ decisionId, resolution, comment }: { decisionId: string; resolution: "approved" | "denied"; comment: string }) =>
      resolveApproval(decisionId, resolution, comment),
    onSuccess: async () => {
      setSelectedApproval(null);
      await queryClient.invalidateQueries({ queryKey: ["command-center"] });
      if (selectedRun) {
        await queryClient.invalidateQueries({ queryKey: ["run-detail", selectedRun.run_id] });
      }
    },
  });

  const data = commandCenterQuery.data;
  const selectedWorkspacePath = useMemo(() => {
    if (!data) {
      return "";
    }
    return data.projects.find((project) => project.project_id === selectedProjectId)?.workspace_path
      || data.projects[0]?.workspace_path
      || data.runtime.local_instance_workspace_path;
  }, [data, selectedProjectId]);

  if (commandCenterQuery.isLoading) {
    return <div className="app-loading">Chargement du command center…</div>;
  }

  if (commandCenterQuery.error || !data) {
    return <div className="app-loading">Le command center est indisponible.</div>;
  }

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div>
          <span className="eyebrow">Managed Agent</span>
          <h1>Command Center</h1>
        </div>
        <div className="top-bar-controls">
          <input
            aria-label="Search runs"
            className="search-input"
            placeholder="Rechercher un run, un projet, une orchestration"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="runtime-badge">
            {data.runtime.app_mode === "lan" ? "LAN sécurisé" : "Local only"}
          </div>
          <button className="primary-button" onClick={() => setLaunchOpen(true)} type="button">
            Nouvelle tâche
          </button>
        </div>
      </header>

      <ExecutiveStrip metrics={data.executive} />

      <section className="hero-band">
        <div>
          <span className="eyebrow">Projet actif</span>
          <h2>{selectedProjectId === "all" ? "Vue globale" : data.projects.find((project) => project.project_id === selectedProjectId)?.display_name}</h2>
        </div>
        <p>
          Poste de pilotage local pour lancer, suivre, approuver et investiguer sans quitter le même espace.
        </p>
      </section>

      <div className="layout-grid">
        <ProjectRail projects={data.projects} selectedProjectId={selectedProjectId} onSelectProject={setSelectedProjectId} />
        <RunWorkspace
          queues={data.queues}
          selectedProjectId={selectedProjectId}
          search={search}
          onSelectRun={(run) => {
            setSelectedRun(run);
            setInvestigationOpen(false);
          }}
        />
        <UrgentActionPanel
          approvals={data.urgent.approvals}
          errors={data.urgent.errors}
          blockedRuns={data.urgent.blocked_runs}
          onOpenApproval={setSelectedApproval}
          onSelectRun={(run) => {
            setSelectedRun(run);
            setInvestigationOpen(false);
          }}
        />
      </div>

      <InvestigationPanel detail={runDetailQuery.data} open={investigationOpen} onOpenChange={setInvestigationOpen} />

      <RunDrawer
        detail={runDetailQuery.data}
        open={Boolean(selectedRun)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedRun(null);
            setInvestigationOpen(false);
          }
        }}
        onOpenInvestigation={() => setInvestigationOpen(true)}
        onRelaunch={() => {
          if (selectedRun) {
            relaunchMutation.mutate(selectedRun.run_id);
          }
        }}
      />

      <LaunchTaskModal
        open={launchOpen}
        onOpenChange={setLaunchOpen}
        onSubmit={(payload) => launchMutation.mutate(payload)}
        orchestrations={data.available_orchestrations}
        selectedWorkspacePath={selectedWorkspacePath}
      />

      <ApprovalModal
        approval={selectedApproval}
        open={Boolean(selectedApproval)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedApproval(null);
          }
        }}
        onResolve={(resolution, comment) => {
          if (selectedApproval) {
            approvalMutation.mutate({
              decisionId: selectedApproval.decision_id,
              resolution,
              comment,
            });
          }
        }}
      />
    </div>
  );
}
