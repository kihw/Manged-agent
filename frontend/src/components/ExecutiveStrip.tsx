import type { ExecutiveMetrics } from "../types";

const METRICS: Array<{ key: keyof ExecutiveMetrics; label: string }> = [
  { key: "active_runs", label: "Runs actifs" },
  { key: "blocked_runs", label: "Bloqués" },
  { key: "pending_approvals", label: "Approvals" },
  { key: "recent_errors", label: "Erreurs" },
  { key: "connected_agents", label: "Agents" },
];

interface ExecutiveStripProps {
  metrics: ExecutiveMetrics;
}

export function ExecutiveStrip({ metrics }: ExecutiveStripProps) {
  return (
    <section className="executive-strip" aria-label="Executive status">
      {METRICS.map((metric) => (
        <article key={metric.key} className="metric-card">
          <span>{metric.label}</span>
          <strong>{metrics[metric.key]}</strong>
        </article>
      ))}
    </section>
  );
}
