import * as Collapsible from "@radix-ui/react-collapsible";
import * as Tabs from "@radix-ui/react-tabs";

import type { RunDetail } from "../types";

interface InvestigationPanelProps {
  detail: RunDetail | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function InvestigationPanel({ detail, open, onOpenChange }: InvestigationPanelProps) {
  return (
    <Collapsible.Root className="investigation-panel" open={open} onOpenChange={onOpenChange}>
      <div className="investigation-header">
        <div>
          <span className="eyebrow">Investigation</span>
          <h2>Profondeur technique</h2>
        </div>
        <Collapsible.Trigger className="ghost-button">
          {open ? "Masquer" : "Afficher"}
        </Collapsible.Trigger>
      </div>
      <Collapsible.Content>
        {detail ? (
          <Tabs.Root className="investigation-tabs" defaultValue="events">
            <Tabs.List className="tabs-list">
              <Tabs.Trigger value="events">Événements</Tabs.Trigger>
              <Tabs.Trigger value="tools">Outils</Tabs.Trigger>
              <Tabs.Trigger value="policy">Policy</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="events" className="tab-panel">
              {detail.events.map((event) => (
                <div key={event.event_id} className="log-row">
                  <strong>{event.type}</strong>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </div>
              ))}
            </Tabs.Content>
            <Tabs.Content value="tools" className="tab-panel">
              {detail.tool_executions.map((tool) => (
                <div key={tool.tool_execution_id} className="log-row">
                  <strong>{tool.tool_name}</strong>
                  <p>{tool.output_summary || tool.input_summary || tool.error_summary || "No summary"}</p>
                </div>
              ))}
            </Tabs.Content>
            <Tabs.Content value="policy" className="tab-panel">
              {detail.policy_decisions.map((decision) => (
                <div key={decision.decision_id} className="log-row">
                  <strong>{decision.action_type}</strong>
                  <p>{decision.reason}</p>
                </div>
              ))}
            </Tabs.Content>
          </Tabs.Root>
        ) : (
          <p className="empty-state">Sélectionne un run pour investiguer.</p>
        )}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
