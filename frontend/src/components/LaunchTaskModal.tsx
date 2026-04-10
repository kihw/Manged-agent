import * as Dialog from "@radix-ui/react-dialog";
import { FormEvent, useEffect, useState } from "react";

import type { LaunchRunPayload } from "../types";

interface LaunchTaskModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: LaunchRunPayload) => void;
  orchestrations: Array<{ orchestration_id: string; name: string }>;
  selectedWorkspacePath: string;
}

export function LaunchTaskModal({
  open,
  onOpenChange,
  onSubmit,
  orchestrations,
  selectedWorkspacePath,
}: LaunchTaskModalProps) {
  const [form, setForm] = useState<LaunchRunPayload>({
    orchestration_id: orchestrations[0]?.orchestration_id || "",
    title: "",
    goal: "",
    workspace_path: selectedWorkspacePath,
    trigger: "manual-ui",
  });

  useEffect(() => {
    setForm((current) => ({
      ...current,
      orchestration_id: current.orchestration_id || orchestrations[0]?.orchestration_id || "",
      workspace_path: selectedWorkspacePath,
    }));
  }, [orchestrations, selectedWorkspacePath]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="modal-content">
          <Dialog.Title>Nouvelle tâche</Dialog.Title>
          <Dialog.Description className="sr-only">
            Configure une orchestration, un objectif et un workspace avant de lancer un run.
          </Dialog.Description>
          <form className="form-grid" onSubmit={handleSubmit}>
            <label>
              Orchestration
              <select
                value={form.orchestration_id}
                onChange={(event) => setForm({ ...form, orchestration_id: event.target.value })}
              >
                {orchestrations.map((orchestration) => (
                  <option key={orchestration.orchestration_id} value={orchestration.orchestration_id}>
                    {orchestration.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Titre
              <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            </label>
            <label>
              Objectif
              <textarea value={form.goal} onChange={(event) => setForm({ ...form, goal: event.target.value })} />
            </label>
            <label>
              Workspace
              <input value={form.workspace_path} onChange={(event) => setForm({ ...form, workspace_path: event.target.value })} />
            </label>
            <label>
              Trigger
              <input value={form.trigger} onChange={(event) => setForm({ ...form, trigger: event.target.value })} />
            </label>
            <div className="form-actions">
              <button className="secondary-button" onClick={() => onOpenChange(false)} type="button">
                Annuler
              </button>
              <button className="primary-button" type="submit">
                Lancer
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
