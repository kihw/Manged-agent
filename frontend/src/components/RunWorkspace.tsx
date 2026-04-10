import type { RunItem } from "../types";

interface RunWorkspaceProps {
  queues: {
    in_progress: RunItem[];
    blocked: RunItem[];
    needs_attention: RunItem[];
    recent: RunItem[];
  };
  selectedProjectId: string;
  search: string;
  onSelectRun: (run: RunItem) => void;
}

function filterRuns(runs: RunItem[], selectedProjectId: string, search: string) {
  const query = search.trim().toLowerCase();
  return runs.filter((run) => {
    const projectMatch = selectedProjectId === "all" || run.project_id === selectedProjectId;
    const searchMatch =
      query.length === 0 ||
      run.title.toLowerCase().includes(query) ||
      run.project_name.toLowerCase().includes(query) ||
      run.orchestration_name.toLowerCase().includes(query);
    return projectMatch && searchMatch;
  });
}

function RunCard({ run, onSelectRun }: { run: RunItem; onSelectRun: (run: RunItem) => void }) {
  return (
    <button className="run-card" onClick={() => onSelectRun(run)} type="button">
      <div className="run-card-head">
        <div>
          <span className="eyebrow">{run.project_name}</span>
          <h3>{run.title}</h3>
        </div>
        <span className={`status-pill status-${run.status}`}>{run.status}</span>
      </div>
      <p>{run.summary || run.goal}</p>
      <div className="run-card-meta">
        <span>{run.orchestration_name}</span>
        <span>{run.current_step || "En attente"}</span>
      </div>
      <div className="run-card-tags">
        {run.has_pending_approval ? <span className="tag urgent">approval</span> : null}
        {run.error_categories.map((category) => (
          <span key={category} className="tag">
            {category}
          </span>
        ))}
      </div>
    </button>
  );
}

function QueueSection({
  title,
  runs,
  emptyMessage,
  onSelectRun,
}: {
  title: string;
  runs: RunItem[];
  emptyMessage: string;
  onSelectRun: (run: RunItem) => void;
}) {
  return (
    <section className="queue-section">
      <div className="queue-header">
        <h2>{title}</h2>
        <span>{runs.length}</span>
      </div>
      <div className="queue-grid">
        {runs.length === 0 ? <p className="empty-state">{emptyMessage}</p> : null}
        {runs.map((run) => (
          <RunCard key={run.run_id} run={run} onSelectRun={onSelectRun} />
        ))}
      </div>
    </section>
  );
}

export function RunWorkspace({ queues, selectedProjectId, search, onSelectRun }: RunWorkspaceProps) {
  return (
    <main className="run-workspace">
      <QueueSection
        title="En cours"
        runs={filterRuns(queues.in_progress, selectedProjectId, search)}
        emptyMessage="Aucun run actif pour ce filtre."
        onSelectRun={onSelectRun}
      />
      <QueueSection
        title="Bloqués"
        runs={filterRuns(queues.blocked, selectedProjectId, search)}
        emptyMessage="Aucun run bloqué."
        onSelectRun={onSelectRun}
      />
      <QueueSection
        title="Nécessitent de l’attention"
        runs={filterRuns(queues.needs_attention, selectedProjectId, search)}
        emptyMessage="Rien de sensible à traiter."
        onSelectRun={onSelectRun}
      />
      <QueueSection
        title="Récents"
        runs={filterRuns(queues.recent, selectedProjectId, search)}
        emptyMessage="Aucun historique récent."
        onSelectRun={onSelectRun}
      />
    </main>
  );
}
