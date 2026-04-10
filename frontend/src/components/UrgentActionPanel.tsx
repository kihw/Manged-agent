import type { ApprovalItem, ErrorItem, RunItem } from "../types";

interface UrgentActionPanelProps {
  approvals: ApprovalItem[];
  errors: ErrorItem[];
  blockedRuns: RunItem[];
  onOpenApproval: (approval: ApprovalItem) => void;
  onSelectRun: (run: RunItem) => void;
}

export function UrgentActionPanel({
  approvals,
  errors,
  blockedRuns,
  onOpenApproval,
  onSelectRun,
}: UrgentActionPanelProps) {
  return (
    <aside className="urgent-panel">
      <section className="urgent-section">
        <div className="urgent-header">
          <span className="eyebrow">Approvals</span>
          <h2>À décider</h2>
        </div>
        {approvals.length === 0 ? <p className="empty-state">Aucune décision en attente.</p> : null}
        {approvals.map((approval) => (
          <button key={approval.decision_id} className="urgent-card" onClick={() => onOpenApproval(approval)} type="button">
            <strong>{approval.title}</strong>
            <span>{approval.reason}</span>
          </button>
        ))}
      </section>

      <section className="urgent-section">
        <div className="urgent-header">
          <span className="eyebrow">Incidents</span>
          <h2>Erreurs critiques</h2>
        </div>
        {errors.length === 0 ? <p className="empty-state">Aucune erreur critique.</p> : null}
        {errors.map((error) => (
          <div key={`${error.run_id}-${error.category}`} className="urgent-card static">
            <strong>{error.title}</strong>
            <span>{error.category}</span>
            <small>{error.message || "Sans message détaillé"}</small>
          </div>
        ))}
      </section>

      <section className="urgent-section">
        <div className="urgent-header">
          <span className="eyebrow">Blocages</span>
          <h2>Runs bloqués</h2>
        </div>
        {blockedRuns.length === 0 ? <p className="empty-state">Aucun blocage.</p> : null}
        {blockedRuns.map((run) => (
          <button key={run.run_id} className="urgent-card" onClick={() => onSelectRun(run)} type="button">
            <strong>{run.title}</strong>
            <span>{run.project_name}</span>
          </button>
        ))}
      </section>
    </aside>
  );
}
