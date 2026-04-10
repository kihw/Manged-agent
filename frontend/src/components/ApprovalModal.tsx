import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

import type { ApprovalItem } from "../types";

interface ApprovalModalProps {
  approval: ApprovalItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onResolve: (resolution: "approved" | "denied", comment: string) => void;
}

export function ApprovalModal({ approval, open, onOpenChange, onResolve }: ApprovalModalProps) {
  const [comment, setComment] = useState("");

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="modal-content">
          <Dialog.Title>Décision opérateur</Dialog.Title>
          <Dialog.Description className="sr-only">
            Confirme ou refuse une action sensible demandee par un run bloque.
          </Dialog.Description>
          {approval ? (
            <>
              <p className="detail-summary">{approval.reason}</p>
              <label>
                Commentaire
                <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
              </label>
              <div className="form-actions">
                <button className="secondary-button" onClick={() => onResolve("denied", comment)} type="button">
                  Refuser
                </button>
                <button className="primary-button" onClick={() => onResolve("approved", comment)} type="button">
                  Approuver
                </button>
              </div>
            </>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
