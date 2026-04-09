# Modèle de données — V1 (minimum viable schema)

## 1) Objectif
Ce document définit le **schéma relationnel minimal** pour supporter :
- versionnement d’agents,
- exécution de tâches et d’étapes,
- appels d’outils,
- approbations humaines,
- traçage/audit,
- sessions d’authentification OAuth/API.

Portée: PostgreSQL en cible principale (SQLite possible en MVP avec adaptations mineures de types/index).

---

## 2) Tables minimales

## `agents`
Représente une entité logique d’agent (stable dans le temps).

Colonnes proposées:
- `id` (UUID, PK)
- `slug` (TEXT, NOT NULL, UNIQUE) — identifiant humain stable (ex: `code-review-agent`)
- `name` (TEXT, NOT NULL)
- `description` (TEXT, NULL)
- `status` (TEXT, NOT NULL, défaut `active`, CHECK in `active|disabled|archived`)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)
- `updated_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Index:
- `uq_agents_slug (slug)`
- `idx_agents_status (status)`

---

## `agent_versions`
Version immutable de la configuration d’un agent.

Colonnes proposées:
- `id` (UUID, PK)
- `agent_id` (UUID, NOT NULL, FK -> `agents.id` ON DELETE CASCADE)
- `version` (INT, NOT NULL, CHECK `version > 0`)
- `system_prompt` (TEXT, NOT NULL)
- `tools_json` (JSONB, NOT NULL) — outils autorisés + paramètres
- `allowed_mcp_servers_json` (JSONB, NOT NULL)
- `policy_profile_json` (JSONB, NOT NULL)
- `limits_json` (JSONB, NOT NULL)
- `is_current` (BOOLEAN, NOT NULL, défaut `false`)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)
- `created_by` (TEXT, NULL)

Contraintes & index:
- **unicité de version par agent**: `UNIQUE (agent_id, version)`
- **au plus une version courante par agent**:
  - index unique partiel PostgreSQL: `UNIQUE (agent_id) WHERE is_current = true`
- `idx_agent_versions_agent_created (agent_id, created_at DESC)`

Remarque: la contrainte `(agent_id, version)` répond explicitement au besoin de versionnement déterministe.

---

## `tasks`
Instance d’exécution d’une mission (run) d’un agent.

Colonnes proposées:
- `id` (UUID, PK)
- `task_key` (TEXT, NOT NULL, UNIQUE) — idempotency/public id
- `agent_id` (UUID, NOT NULL, FK -> `agents.id` ON DELETE RESTRICT)
- `agent_version_id` (UUID, NOT NULL, FK -> `agent_versions.id` ON DELETE RESTRICT)
- `goal` (TEXT, NOT NULL)
- `input_json` (JSONB, NULL)
- `repo_path` (TEXT, NULL)
- `status` (TEXT, NOT NULL, CHECK in `queued|running|waiting_approval|completed|failed|canceled`)
- `priority` (SMALLINT, NOT NULL, défaut `100`)
- `requested_by` (TEXT, NULL)
- `started_at` (TIMESTAMPTZ, NULL)
- `finished_at` (TIMESTAMPTZ, NULL)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Contraintes & index:
- `uq_tasks_task_key (task_key)`
- `idx_tasks_agent_created (agent_id, created_at DESC)`
- `idx_tasks_status_created (status, created_at)`
- `CHECK (finished_at IS NULL OR started_at IS NOT NULL)`

---

## `task_steps`
Étapes internes d’une tâche (planner/executor/critic/tool-call/etc.).

Colonnes proposées:
- `id` (UUID, PK)
- `task_id` (UUID, NOT NULL, FK -> `tasks.id` ON DELETE CASCADE)
- `step_no` (INT, NOT NULL, CHECK `step_no > 0`)
- `phase` (TEXT, NOT NULL, CHECK in `plan|execute|critic|finalize|tool`)
- `status` (TEXT, NOT NULL, CHECK in `queued|running|waiting_approval|completed|failed|canceled`)
- `input_json` (JSONB, NULL)
- `output_json` (JSONB, NULL)
- `error_json` (JSONB, NULL)
- `started_at` (TIMESTAMPTZ, NULL)
- `finished_at` (TIMESTAMPTZ, NULL)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Contraintes & index:
- ordre unique par tâche: `UNIQUE (task_id, step_no)`
- `idx_task_steps_task_phase (task_id, phase)`
- `idx_task_steps_status (status)`

---

## `tool_executions`
Audit d’exécutions d’outils (shell/fs/git/tests/MCP). Peut être rattaché à une étape.

Colonnes proposées:
- `id` (UUID, PK)
- `task_id` (UUID, NOT NULL, FK -> `tasks.id` ON DELETE CASCADE)
- `task_step_id` (UUID, NULL, FK -> `task_steps.id` ON DELETE SET NULL)
- `tool_name` (TEXT, NOT NULL)
- `tool_type` (TEXT, NOT NULL, CHECK in `local|mcp|llm_gateway`)
- `request_json` (JSONB, NOT NULL)
- `response_json` (JSONB, NULL)
- `exit_code` (INT, NULL)
- `latency_ms` (INT, NULL, CHECK `latency_ms >= 0`)
- `status` (TEXT, NOT NULL, CHECK in `queued|running|waiting_approval|completed|failed|canceled`)
- `redaction_applied` (BOOLEAN, NOT NULL, défaut `true`)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Contraintes & index:
- `idx_tool_exec_task_created (task_id, created_at)`
- `idx_tool_exec_tool_status (tool_name, status)`
- `idx_tool_exec_step (task_step_id)`

---

## `approvals`
Gestion des demandes d’approbation humaine et de leur décision.

Colonnes proposées:
- `id` (UUID, PK)
- `task_id` (UUID, NOT NULL, FK -> `tasks.id` ON DELETE CASCADE)
- `task_step_id` (UUID, NULL, FK -> `task_steps.id` ON DELETE SET NULL)
- `approval_type` (TEXT, NOT NULL, CHECK in `tool_execution|network_access|budget_overrun|sensitive_write`)
- `status` (TEXT, NOT NULL, CHECK in `queued|running|waiting_approval|completed|failed|canceled`)
- `reason` (TEXT, NULL)
- `requested_by` (TEXT, NULL)
- `decided_by` (TEXT, NULL)
- `decided_at` (TIMESTAMPTZ, NULL)
- `expires_at` (TIMESTAMPTZ, NULL)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Contraintes & index:
- `idx_approvals_task_status (task_id, status)`
- **une approbation en attente par scope** (optionnel mais recommandé):
  - `UNIQUE (task_id, task_step_id, approval_type, status)` avec contrainte applicative limitant `status='waiting_approval'`
  - en PostgreSQL: unique partiel `UNIQUE(task_id, task_step_id, approval_type) WHERE status='waiting_approval'`

---

## `trace_events`
Événements de traçage corrélés (OTel-friendly), volume potentiellement élevé.

Colonnes proposées:
- `id` (BIGSERIAL, PK) ou UUID si homogénéité stricte
- `trace_id` (TEXT, NOT NULL)
- `span_id` (TEXT, NULL)
- `parent_span_id` (TEXT, NULL)
- `task_id` (UUID, NULL, FK -> `tasks.id` ON DELETE SET NULL)
- `task_step_id` (UUID, NULL, FK -> `task_steps.id` ON DELETE SET NULL)
- `tool_execution_id` (UUID, NULL, FK -> `tool_executions.id` ON DELETE SET NULL)
- `event_type` (TEXT, NOT NULL)
- `severity` (TEXT, NOT NULL, CHECK in `debug|info|warn|error`)
- `message` (TEXT, NULL)
- `attributes_json` (JSONB, NOT NULL)
- `token_usage_json` (JSONB, NULL)
- `cost_estimate_usd` (NUMERIC(12,6), NULL)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Index:
- `idx_trace_events_trace_created (trace_id, created_at)`
- `idx_trace_events_task_created (task_id, created_at)`
- `idx_trace_events_type_created (event_type, created_at)`
- `idx_trace_events_created_brin USING BRIN(created_at)` pour gros volumes

---

## `auth_sessions`
Sessions d’authentification (OAuth/API key déléguée), sans exposer les secrets en clair.

Colonnes proposées:
- `id` (UUID, PK)
- `subject_type` (TEXT, NOT NULL, CHECK in `user|service_account`)
- `subject_id` (TEXT, NOT NULL)
- `provider` (TEXT, NOT NULL, ex: `openai`)
- `auth_mode` (TEXT, NOT NULL, CHECK in `oauth|api_key|auto`)
- `access_token_ref` (TEXT, NULL) — référence coffre (pas le token)
- `refresh_token_enc` (BYTEA, NULL) — chiffré KMS/clé locale rotatable
- `scopes` (TEXT[], NULL)
- `status` (TEXT, NOT NULL, CHECK in `active|expired|revoked`)
- `last_used_at` (TIMESTAMPTZ, NULL)
- `expires_at` (TIMESTAMPTZ, NULL)
- `created_at` (TIMESTAMPTZ, NOT NULL, défaut `now()`)

Contraintes & index:
- éviter doublons de session active par couple principal:
  - unique partiel `UNIQUE(subject_type, subject_id, provider) WHERE status='active'`
- `idx_auth_sessions_expires (expires_at)`
- `idx_auth_sessions_subject (subject_type, subject_id)`

---

## 3) Mapping unique « état logique → état stocké/API »

Ce mapping est **canonique** pour tous les champs `status` exposés via API et persistés en base.

| État logique | État stocké/API (canonique) | Synonymes interdits |
|---|---|---|
| En file d’attente | `queued` | `pending` |
| En cours d’exécution | `running` | `started`, `in_progress` |
| En attente d’approbation humaine | `waiting_approval` | `awaiting_approval`, `paused_for_approval` |
| Terminé avec succès | `completed` | `succeeded`, `done` |
| Terminé en échec | `failed` | `error` |
| Arrêté avant fin | `canceled` | `cancelled`, `aborted` |

---

## 4) Diagramme relationnel (texte + cardinalités)

```text
agents (1) ────────────────< (N) agent_versions
  │                               │
  │                               └── contrainte UNIQUE (agent_id, version)
  │
  └───────────────< (N) tasks >─────────────── (1) agent_versions (snapshot utilisé)
                    │
                    ├──────────────< (N) task_steps
                    │                  │
                    │                  ├──────────────< (N) tool_executions
                    │                  └──────────────< (N) approvals
                    │
                    ├──────────────< (N) tool_executions
                    ├──────────────< (N) approvals
                    └──────────────< (N) trace_events

trace_events (N) peut aussi référencer optionnellement:
- task_steps (N:1)
- tool_executions (N:1)

auth_sessions est indépendant du graphe d’exécution (table transverse),
lié logiquement à requested_by/subject_id côté application.
```

Cardinalités clés:
- `agents 1..N agent_versions`
- `agents 1..N tasks`
- `agent_versions 1..N tasks` (snapshot figé à l’instant d’exécution)
- `tasks 1..N task_steps`
- `tasks 1..N tool_executions`
- `tasks 1..N approvals`
- `tasks 1..N trace_events`
- `task_steps 1..N tool_executions` (optionnel)
- `task_steps 1..N approvals` (optionnel)

---

## 5) Stratégie de migrations

## 5.1 Convention de nommage
Format recommandé (timestamp UTC + slug):
- `YYYYMMDDHHMMSS__<scope>__<action>.sql`
- Exemples:
  - `20260409103000__core__create_agents.sql`
  - `20260409104000__core__create_tasks_and_steps.sql`
  - `20260409105000__obs__create_trace_events.sql`

Toujours livrer par paire:
- `up` (apply)
- `down` (rollback)

## 4.2 Principes d’évolution (backward-compatible d’abord)
1. **Expand/Contract**:
   - Expand: ajouter colonnes/tables nullable, nouveaux index, double-write.
   - Migration applicative.
   - Backfill async si nécessaire.
   - Contract: supprimer ancien schéma dans une release ultérieure.
2. Ne pas renommer/supprimer une colonne utilisée par la version N-1 sans phase transitoire.
3. Ajouter des contraintes strictes en 2 temps:
   - ajouter la colonne nullable,
   - backfill,
   - passer en NOT NULL.
4. Pour index lourds PostgreSQL: `CREATE INDEX CONCURRENTLY`.

## 4.3 Rollback
- Toute migration `up` doit avoir son `down` testée en environnement de staging.
- Exceptions (opérations non réversibles) documentées explicitement dans le fichier migration avec procédure manuelle.
- En cas de rollback applicatif, garantir que la DB est compatible avec version N-1 (minimum une release).

## 4.4 Gouvernance de migrations
- Une PR ne mélange pas migration destructrice + changement applicatif sans feature flag.
- Toujours inclure:
  - estimation lock/temps,
  - plan de backfill,
  - plan de rollback,
  - monitoring post-déploiement.

---

## 5) Politique de rétention & purge

## 5.1 Classification des données
- **Durable (longue durée)**: `agents`, `agent_versions`, `tasks`, `task_steps`, `approvals`.
- **Volumique (courte/moyenne durée)**: `trace_events`, payloads lourds de `tool_executions`, artefacts externes.
- **Sensible**: `auth_sessions` (tokens/chiffrement).

## 5.2 Rétention recommandée
- `trace_events`: 30 jours (90 jours en mode audit renforcé).
- `tool_executions.request_json/response_json`: 30 jours, puis redaction/suppression partielle.
- Métadonnées minimales d’exécution (`status`, `latency_ms`, `created_at`): 180 jours.
- `approvals`: 365 jours (audit).
- `tasks` + `task_steps`: 365 jours (ou politique produit).
- `auth_sessions`:
  - sessions expirées/révokées: purge à J+7,
  - refresh tokens invalides: suppression immédiate.

## 5.3 Mécanisme de purge
Approche hybride:
1. **Partition temporelle** (`trace_events` mensuel) + drop de partitions expirées.
2. Job quotidien `retention_worker`:
   - purge hard-delete des sessions auth expirées,
   - suppression/redaction des payloads volumineux,
   - compactage éventuel des tables.
3. Pour artefacts externes (filesystem/object storage):
   - lifecycle policy alignée sur la DB,
   - suppression via pointeurs (`artifact_uri`) et tâche de garbage collection.

## 5.4 Sécurité & conformité purge
- Purge **irréversible** pour secrets/tokens.
- Journaliser les opérations de purge (compteurs, tables impactées, durée).
- Prévoir mode `legal_hold` (suspension purge ciblée par `task_id`/tenant).

---

## 6) Notes d’implémentation
- Tous les JSON doivent être validés côté application (JSON Schema versionné).
- `updated_at` maintenu par trigger DB ou couche ORM.
- Les FK critiques (`tasks.agent_version_id`) garantissent la reproductibilité d’un run.
- Prévoir UUID v7 quand disponible pour meilleures perfs d’indexation temporelle.
