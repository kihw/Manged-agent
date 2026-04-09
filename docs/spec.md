# Spécification complète — Plateforme d’agents managés localement (LLM via Codex)

## 1. Objectif
Construire une plateforme d’agents "managed" avec orchestration locale, outils et données locales, et inférence LLM via Codex (API key ou OAuth subscription).

## 2. Périmètre
### Inclus
- Control plane local (API, orchestration, queue, policy engine)
- LLM Gateway local (auth API key/OAuth, budgets, retries)
- Runtime outils sandboxé local (fs/git/shell/tests)
- Intégration MCP (registry + ACL)
- Stockage local (state, artefacts, observabilité)

### Exclu V1
- Fine-tuning
- Multi-cloud
- Marketplace public d’agents

## 3. Exigences fonctionnelles
1. Créer/versionner des définitions d’agents
2. Lancer des tâches avec workflow planner/executor/critic
3. Exécuter des outils locaux avec policy checks
4. Appeler Codex via gateway centralisée
5. Supporter MCP server allowlist par agent
6. Journaliser traces, coûts, latences, et décisions policy

## 4. Exigences non fonctionnelles
- Sécurité: secrets masqués, chiffrement des refresh tokens
- Fiabilité: retries bornés + idempotence des étapes
- Observabilité: logs structurés, traces OTel, métriques Prometheus
- Scalabilité: workers horizontaux via queue
- Gouvernance: approval humain pour actions sensibles

## 5. Architecture cible
```text
[CLI/UI]
   |
   v
[API Gateway locale]
   |
   v
[Control Plane]
 - Agent Manager
 - Task Manager
 - Scheduler/Queue
 - Policy Engine
   |\
   | \----------------------------+
   v                              v
[Tool Runtime sandboxé]      [LLM Gateway]
 - fs/git/shell/tests         - auth resolver api_key/oauth/auto
 - MCP client                 - retries/timeouts/rate limits
 - network off par défaut     - redaction + budget guard
   |
   v
[Data Plane local]
 - Postgres (ou SQLite en MVP)
 - Redis (queue/cache)
 - Artifacts storage

[Observability]
 - OpenTelemetry
 - Prometheus/Grafana
 - Loki
```

## 6. Contrats de données
### AgentDefinition
- `agent_id`, `version`, `description`
- `system_prompt`
- `tools[]`
- `allowed_mcp_servers[]`
- `policy_profile`
- `limits {max_iterations,max_tokens,max_cost,max_duration}`
- `approval_rules`

### AgentTask
- `task_id`, `agent_id`, `goal`, `repo_path`, `constraints[]`
- `auth_context {mode,user_id}`
- `status`

### TraceEvent
- `trace_id`, `task_id`, `phase`, `latency_ms`
- `token_usage`, `cost_estimate`
- `auth_mode`, `timestamp`

## 7. LLM Gateway
### Modes d’auth
- `api_key`: service account
- `oauth`: utilisateur connecté
- `auto`: OAuth si user context valide sinon API key (si policy autorise)

### Responsabilités
- Normaliser appels vers Codex
- Gérer refresh token OAuth
- Appliquer quotas/budgets/timeout
- Redacter PII/secrets
- Produire métriques et traces

## 8. Policy Engine
### Règles
- allow/deny outils
- contraintes chemins FS
- allowlist commandes shell
- policy réseau (deny par défaut)
- règles d’approbation humaine
- garde-fous budgets (coût/tokens/temps)

## 9. MCP
- Registry central des serveurs MCP
- ACL par agent et environnement
- Timeout/retry bornés
- Audit des appels (inputs/outputs redacted)

## 10. API minimale
- `POST /v1/agents`
- `GET /v1/agents/{agent_id}`
- `POST /v1/tasks`
- `GET /v1/tasks/{task_id}`
- `POST /v1/tasks/{task_id}/approve`
- `GET /v1/traces/{task_id}`
- `POST /v1/auth/oauth/callback`
- `GET /v1/auth/status`

## 11. Déploiement
- Dev: docker-compose
- Staging/Prod: même architecture avec scaling des workers
- Secrets: variables d’environnement + vault interne recommandé

## 12. Critères d’acceptation
- Exécution stable sur 100 tâches de validation
- 0 action sensible sans approval en mode strict
- Corrélation complète task/tool/llm dans les traces
- Dashboard coût/latence opérationnel

## 13. Standard de logs JSON
Tous les composants (`api`, `worker`, `gateway`, `scheduler`, `policy-engine`) doivent produire des logs JSON "one-line" UTF-8.

### Champs obligatoires
- `timestamp` (RFC3339 UTC, ex. `2026-04-09T12:34:56.123Z`)
- `level` (`DEBUG|INFO|WARN|ERROR`)
- `task_id` (identifiant métier de la tâche, ou `null` explicite hors contexte)
- `trace_id` (W3C Trace Context compatible, 16-byte hex)
- `component` (nom logique du service émetteur)

### Champs recommandés
- `span_id`, `message`, `event`, `error.code`, `error.message`
- `tool.name`, `tool.exit_code`, `llm.model`, `llm.tokens_in`, `llm.tokens_out`
- `cost.usd`, `queue.name`, `queue.wait_ms`, `approval.required`, `approval.wait_ms`

### Exigences d’implémentation
- Pas de logs texte non structurés en production.
- Redaction systématique des secrets/PII avant émission.
- Échantillonnage autorisé uniquement pour `DEBUG`, jamais pour `WARN|ERROR`.
- Le champ `trace_id` doit correspondre à la trace OTel active quand disponible.

## 14. Métriques Prometheus
### Nomenclature
Préfixe métriques: `managed_agent_`.

### Latence LLM (p50/p95/p99)
- Instrumentation: histogramme `managed_agent_llm_latency_seconds`.
- Labels minimaux: `model`, `auth_mode`, `component`, `status`.
- SLO de référence:
  - p50 < 1.5s
  - p95 < 4s
  - p99 < 8s
- Requêtes PromQL cible:
  - p50: `histogram_quantile(0.50, sum(rate(managed_agent_llm_latency_seconds_bucket[5m])) by (le, model))`
  - p95: `histogram_quantile(0.95, sum(rate(managed_agent_llm_latency_seconds_bucket[5m])) by (le, model))`
  - p99: `histogram_quantile(0.99, sum(rate(managed_agent_llm_latency_seconds_bucket[5m])) by (le, model))`

### Taux d’échec outils
- Compteurs:
  - `managed_agent_tool_calls_total{tool,component}`
  - `managed_agent_tool_failures_total{tool,component,reason}`
- KPI:
  - `sum(rate(managed_agent_tool_failures_total[5m])) / sum(rate(managed_agent_tool_calls_total[5m]))`

### Coût par tâche
- Métriques:
  - compteur `managed_agent_task_cost_usd_total{agent_id,component}`
  - histogramme optionnel `managed_agent_task_cost_usd_bucket{agent_id}`
- KPI:
  - coût moyen: `sum(rate(managed_agent_task_cost_usd_total[15m])) / sum(rate(managed_agent_tasks_completed_total[15m]))`
  - coût p95: `histogram_quantile(0.95, sum(rate(managed_agent_task_cost_usd_bucket[1h])) by (le, agent_id))`

### Temps d’attente approval
- Histogramme: `managed_agent_approval_wait_seconds{policy_profile,component}`
- Quantiles requis: p50/p95 et max via `max_over_time`.

## 15. Propagation de contexte OTel (API, worker, gateway)
### Standard retenu
- W3C Trace Context (`traceparent`, `tracestate`) + `baggage`.
- Propagator unique configuré dans tous les services: `tracecontext,baggage`.

### Flux API -> worker -> gateway
1. **API**: crée/continue la trace entrante HTTP, ajoute `task_id`, `agent_id`, `user_id` en attributs de span.
2. **API vers queue**: injecte `traceparent` et `baggage` dans les métadonnées du message (`headers`/`properties`).
3. **Worker**: extrait le contexte au dequeue, crée un span consumer enfant du span API.
4. **Worker vers gateway**: propage le même contexte via en-têtes HTTP OTEL.
5. **Gateway**: crée un span server interne puis span client LLM; conserve le `trace_id` dans logs JSON.

### Règles d’attribution
- Attributs transverses minimaux: `task.id`, `agent.id`, `component`, `env`, `approval.required`.
- Interdiction de stocker secrets/tokens dans `baggage`.
- Tout changement de thread/process doit réactiver explicitement le contexte.

## 16. Dashboards Grafana cibles et alerting minimal
### Dashboards
1. **Executive Overview**
   - tâches lancées/terminées/échouées
   - coût total journalier et coût moyen par tâche
   - latence LLM p50/p95/p99
2. **Runtime & Queue**
   - profondeur de queue, âge du plus vieux message
   - throughput workers, temps moyen d’exécution outil
   - taux d’échec outils par type
3. **Approval & Governance**
   - volume d’approvals requis vs auto-approvés
   - temps d’attente approval p50/p95
   - tâches bloquées > 15 min en attente humaine
4. **Gateway Health**
   - taux 4xx/5xx par modèle/fournisseur
   - retries/timeouts/circuit breaker events
   - saturation quotas/budget guard triggers

### Alertes minimales
- **Erreur > seuil**
  - Critique: taux d’erreur global > 5% sur 5 min.
  - Warning: taux d’erreur outils > 10% sur 10 min pour un `tool`.
- **Latence > seuil**
  - Critique: p95 latence LLM > 4s sur 10 min.
  - Warning: p99 latence LLM > 8s sur 10 min.
- **Queue backlog**
  - Critique: backlog > 1000 messages pendant 10 min.
  - Warning: message le plus ancien > 5 min.

### Exigences alerting
- Chaque alerte inclut `runbook_url`, `dashboard_uid`, `component`.
- Déduplication par `alertname + component + env`.
- Notification vers canal on-call + ticket automatique si > 30 min.
