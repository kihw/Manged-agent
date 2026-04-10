import * as Dialog from "@radix-ui/react-dialog";

import type { RunDetail } from "../types";

interface RunDrawerProps {
  detail: RunDetail | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpenInvestigation: () => void;
  onRelaunch: () => void;
}

export function RunDrawer({ detail, open, onOpenChange, onOpenInvestigation, onRelaunch }: RunDrawerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="drawer-content" aria-label="Run details">
          <Dialog.Description className="sr-only">
            Resume operatoire d&apos;un run avec acces rapide a la relance et a l&apos;investigation.
          </Dialog.Description>
          <div className="drawer-head">
            <div>
              <span className="eyebrow">Run sélectionné</span>
              <Dialog.Title>{detail?.task.title || "Chargement..."}</Dialog.Title>
            </div>
            <Dialog.Close className="ghost-button" type="button">
              Fermer
            </Dialog.Close>
          </div>

          {detail ? (
            <div className="drawer-body">
              <div className="detail-grid">
                <div>
                  <span className="detail-label">Statut</span>
                  <strong>{detail.run.status}</strong>
                </div>
                <div>
                  <span className="detail-label">Projet</span>
                  <strong>{detail.run.workspace_path}</strong>
                </div>
                <div>
                  <span className="detail-label">Orchestration</span>
                  <strong>{detail.orchestration?.name || detail.run.orchestration_id}</strong>
                </div>
                <div>
                  <span className="detail-label">Étape</span>
                  <strong>{detail.task.current_step || "Aucune"}</strong>
                </div>
              </div>

              <p className="detail-summary">{detail.run.summary || detail.task.goal}</p>

              <div className="drawer-actions">
                <button className="primary-button" onClick={onOpenInvestigation} type="button">
                  Investiguer
                </button>
                <button className="secondary-button" onClick={onRelaunch} type="button">
                  Relancer
                </button>
              </div>

              <section className="drawer-panel">
                <h3>Décisions</h3>
                {detail.policy_decisions.length === 0 ? <p className="empty-state">Aucune policy decision.</p> : null}
                {detail.policy_decisions.map((decision) => (
                  <div key={decision.decision_id} className="list-row">
                    <strong>{decision.action_type}</strong>
                    <span>{decision.status}</span>
                  </div>
                ))}
              </section>
            </div>
          ) : (
            <p className="empty-state">Chargement du détail du run…</p>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
