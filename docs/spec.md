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

### AuditDecision
Format normalisé pour toute décision du moteur de policy.

```json
{
  "decision_id": "aud_01JXYZ...",
  "task_id": "task_123",
  "actor": {
    "type": "agent|user|system",
    "id": "agent.buildbot"
  },
  "matched_rule": {
    "category": "tool_denylist",
    "name": "deny_git_push_without_approval",
    "priority": 20
  },
  "decision": "allow|deny|require_approval",
  "reason": "git.push requires human approval in strict profile",
  "timestamp": "2026-04-09T12:00:00Z"
}
```

Champs minimaux obligatoires: `matched_rule`, `reason`, `timestamp`, `actor`.

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

### Versioning et évaluation
- Chaque policy possède `policy_version` (semver) pour permettre migration/rollback.
- L’évaluation suit `rule_evaluation_order` pour garantir une priorité explicite.
- La résolution de conflits est fixée à `deny-overrides`: toute règle `deny` l’emporte sur un `allow` concurrent.

### Policy Evaluation Flow
Pseudo-flow appliqué pour chaque action outil/LLM/MCP.

1. **Validation input**
   - Vérifier la conformité du payload contre `policy.schema.json`.
   - Rejeter immédiatement les actions avec paramètres invalides.
2. **Matching règle**
   - Itérer dans l’ordre `rule_evaluation_order`.
   - Identifier la première règle applicable par catégorie (ou toutes selon implémentation interne) et conserver la priorité.
3. **Décision**
   - Appliquer `deny-overrides`.
   - Produire `allow`, `deny` ou `require_approval`.
4. **Journalisation**
   - Émettre un événement `AuditDecision` structuré.
   - Inclure règle matchée, raison, actor et timestamp UTC.

### Cas d’approbation humaine obligatoire
Les actions suivantes doivent déclencher `require_approval` avant exécution:
- `git.push` (toute opération de publication distante)
- `shell.sensitive` (ex: suppression récursive, permissions système, commandes destructrices)
- `network.enable` (activation d’accès réseau global ou élargissement de scope)

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

## 12. Exemples de policies

### strict
```json
{
  "policy_version": "1.0.0",
  "policy_profile": "strict",
  "rule_evaluation_order": [
    "budget_limits",
    "tool_denylist",
    "tool_allowlist",
    "command_allowlist",
    "filesystem",
    "network",
    "mcp_allowlist",
    "require_human_approval"
  ],
  "conflict_resolution": "deny-overrides",
  "tool_allowlist": ["fs.read", "git.status", "tests.run"],
  "tool_denylist": ["shell.exec", "git.push"],
  "network_default": "deny",
  "require_human_approval": ["git.push", "shell.sensitive", "network.enable"]
}
```

### balanced
```json
{
  "policy_version": "1.1.0",
  "policy_profile": "balanced",
  "rule_evaluation_order": [
    "budget_limits",
    "tool_denylist",
    "tool_allowlist",
    "command_allowlist",
    "filesystem",
    "network",
    "mcp_allowlist",
    "require_human_approval"
  ],
  "conflict_resolution": "deny-overrides",
  "tool_allowlist": ["fs.read", "fs.write", "git.status", "git.commit", "tests.run"],
  "tool_denylist": ["git.force_push"],
  "network_default": "deny",
  "network_allow_hosts": ["api.openai.com"],
  "require_human_approval": ["git.push", "shell.sensitive", "network.enable"]
}
```

### dev
```json
{
  "policy_version": "1.2.0",
  "policy_profile": "dev",
  "rule_evaluation_order": [
    "budget_limits",
    "tool_denylist",
    "tool_allowlist",
    "command_allowlist",
    "filesystem",
    "network",
    "mcp_allowlist",
    "require_human_approval"
  ],
  "conflict_resolution": "deny-overrides",
  "tool_allowlist": ["fs.read", "fs.write", "shell.exec", "git.status", "git.commit", "tests.run"],
  "tool_denylist": [],
  "network_default": "allow",
  "require_human_approval": ["git.push", "shell.sensitive", "network.enable"]
}
```

## 13. Critères d’acceptation
- Exécution stable sur 100 tâches de validation
- 0 action sensible sans approval en mode strict
- Corrélation complète task/tool/llm dans les traces
- Dashboard coût/latence opérationnel

## 13. Cycle de vie d’une tâche (pas à pas)
1. **Création (`queued`)**  
   Le client appelle `POST /v1/tasks`. La tâche reçoit un `task_id` et un `trace_id`, puis est placée en file d’attente avec le statut `queued`.
2. **Planification (`running`)**  
   Le scheduler assigne la tâche à un worker. Le worker crée un premier `step_id` et passe la tâche en `running`.
3. **Exécution d’étapes (`running`)**  
   Chaque étape (`TaskStep`) exécute zéro ou plusieurs appels outils (`ToolExecution`) identifiés par `tool_call_id`. Les événements sont publiés dans les traces avec corrélation `task_id` / `trace_id` / `step_id` / `tool_call_id`.
4. **Validation policy (`waiting_approval` si nécessaire)**  
   Si une action est sensible, une `ApprovalRequest` est émise et la tâche bascule en `waiting_approval` jusqu’à décision via `POST /v1/tasks/{task_id}/approve`.
5. **Reprise après approbation (`running`)**  
   Après approbation, la tâche repasse en `running`, poursuit les étapes restantes et génère les `Artifact` nécessaires.
6. **Finalisation (`completed` / `failed` / `canceled`)**  
   - `completed` si tous les objectifs sont atteints,  
   - `failed` en cas d’erreur non récupérable,  
   - `canceled` si arrêt explicite opérateur/système.
7. **Consultation et audit**  
   `GET /v1/tasks/{task_id}` retourne l’état consolidé (étapes, outils, approbations, artefacts). `GET /v1/traces/{task_id}` expose la chronologie détaillée corrélée.
## 13. Structure des modules (squelette MVP)
```text
app/
  main.py                # Entrée FastAPI + healthcheck + wiring des routers /v1
  routers/
    agents.py            # Endpoints API agents (lecture/écriture des définitions)
    tasks.py             # Endpoints API tâches (création, statut, approbation)
    auth.py              # Endpoints auth (status, callback OAuth)
    traces.py            # Endpoints d’accès aux traces par tâche
  services/
    agent_service.py     # Contrats internes pour la gestion d’agents
    task_service.py      # Contrats internes pour l’orchestration des tâches
    auth_service.py      # Contrats internes pour la résolution auth/OAuth
    policy_service.py    # Contrats internes pour les décisions policy/budget
worker.py                # Boucle de consommation queue (placeholder) + logs structurés
```

### Responsabilités par package
- `app.main`: bootstrap de l’API, point de montage des routers versionnés, endpoint de liveness/readiness simplifié (`/healthz`).
- `app.routers`: couche HTTP uniquement (validation de payloads, mapping requête/réponse), sans logique métier complexe.
- `app.services`: interfaces/protocoles pour figer les contrats entre API, orchestrateur et adapters (DB, queue, gateway).
- `worker.py`: exécution asynchrone côté backplane, polling queue et journalisation structurée orientée observabilité.
