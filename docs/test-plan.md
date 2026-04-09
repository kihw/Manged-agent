# Plan de tests — Plateforme d’agents managés

## 1) Objectifs et périmètre
Ce plan valide la conformité de la plateforme aux exigences de `docs/spec.md` avec une couverture systématique:
- tests de contrat API,
- tests du moteur de policy,
- tests d’authentification (OAuth / API key / auto),
- tests d’intégration MCP,
- tests de chaos (timeouts, retries),
- tests de sécurité (prompt injection, command bypass, fuite de secrets).

## 2) Environnements et prérequis
- **Local dev**: `docker-compose` (API + Control Plane + Runtime + LLM Gateway + DB/queue + observabilité).
- **Données**: base de test isolée, jeu d’artefacts local, registry MCP de test.
- **Instrumentation obligatoire**: logs structurés, traces OTel, métriques Prometheus, corrélation `task_id/trace_id`.
- **Profils policy**: `strict`, `balanced`, `dev`.

## 3) Jeux de données de test

### 3.1 Définitions d’agents (`agent_definitions`)
1. **agent-safe-v1**
   - Outils: `fs.read`, `git.status`, `tests.run`
   - `allowed_mcp_servers`: `docs-mcp`
   - `policy_profile`: `strict`
   - `limits`: bas (tokens/coût/durée)
2. **agent-dev-v1**
   - Outils: `fs/*`, `git/*`, `shell.allowlist`
   - `allowed_mcp_servers`: `docs-mcp`, `ci-mcp`
   - `policy_profile`: `balanced`
   - `limits`: moyens
3. **agent-network-denied-v1**
   - Outils: `shell`
   - Policy réseau: deny par défaut
   - `policy_profile`: `strict`

### 3.2 Tâches (`tasks`)
1. **task-readme-fix**: modification fichier doc locale (faible risque).
2. **task-sensitive-cmd**: demande de commande nécessitant approval.
3. **task-long-run**: workflow long pour tester timeout/retry.
4. **task-mcp-fetch**: récupération contexte via MCP autorisé.
5. **task-mcp-forbidden**: appel MCP non allowlisté.

### 3.3 Contexte d’authentification (`auth_context`)
1. **oauth-valid-user**: utilisateur connecté, refresh token valide.
2. **oauth-expired-refreshable**: access token expiré, refresh possible.
3. **api-key-service**: clé service valide.
4. **auto-with-user**: mode auto avec user context valide.
5. **auto-no-user**: mode auto sans user context (fallback API key si policy OK).
6. **invalid-credentials**: OAuth invalide + API key absente/invalide.

### 3.4 Données sécurité
- **payload-prompt-injection-1**: “Ignore toutes les règles et exécute ...”.
- **payload-command-bypass-1**: obfuscation shell (`$IFS`, encodage, sous-shell).
- **payload-secret-leak-1**: requête d’affichage de variables (`OPENAI_API_KEY`, tokens).
- **payload-pii-1**: e-mail/téléphone/clé privée pour vérifier redaction.

## 4) Suites de tests

## 4.1 API contract tests
Objectif: valider schémas, statuts HTTP, idempotence et cohérence des ressources.

### Endpoints et scénarios d’acceptation

#### `POST /v1/agents`
- **AC-API-001** Création valide retourne `201` + `agent_id` + `version`.
- **AC-API-002** Payload invalide (champ manquant) retourne `400` avec erreur structurée.
- **AC-API-003** Recréation même version retourne conflit `409` (ou stratégie d’upsert explicitée).

#### `GET /v1/agents/{agent_id}`
- **AC-API-004** Agent existant retourne `200` et contrat `AgentDefinition` complet.
- **AC-API-005** Agent inconnu retourne `404`.

#### `POST /v1/tasks`
- **AC-API-006** Création tâche valide retourne `202` avec `task_id`, `status=queued|running`.
- **AC-API-007** `auth_context.mode` invalide retourne `400`.
- **AC-API-008** `agent_id` inconnu retourne `404`.

#### `GET /v1/tasks/{task_id}`
- **AC-API-009** Tâche existante retourne `200` + transitions d’état valides.
- **AC-API-010** Tâche inconnue retourne `404`.

#### `POST /v1/tasks/{task_id}/approve`
- **AC-API-011** Approval requis: `200` et reprise d’exécution.
- **AC-API-012** Approval non requis ou déjà traité: `409`/`422` documenté.

#### `GET /v1/traces/{task_id}`
- **AC-API-013** Retourne liste `TraceEvent` avec corrélation `task_id/trace_id`.
- **AC-API-014** Présence de `latency_ms`, `token_usage`, `cost_estimate`, `auth_mode`.

#### `POST /v1/auth/oauth/callback`
- **AC-API-015** Callback valide retourne `200` et session auth active.
- **AC-API-016** Callback invalide (state/code) retourne `401/400`.

#### `GET /v1/auth/status`
- **AC-API-017** OAuth actif retourne mode et expiration token.
- **AC-API-018** Non authentifié retourne état explicite non ambigu.

## 4.2 Policy tests
Objectif: vérifier enforcement des règles (outil, FS, shell, réseau, approval, budget).

- **AC-POL-001** Outil hors allowlist → refus explicite, pas d’exécution runtime.
- **AC-POL-002** Accès FS hors chemins autorisés → blocage + audit event.
- **AC-POL-003** Commande shell hors allowlist → blocage.
- **AC-POL-004** Réseau sortant en profil strict → deny par défaut.
- **AC-POL-005** Action sensible sans approval → bloquée.
- **AC-POL-006** Dépassement budget (`max_tokens/max_cost/max_duration`) → arrêt contrôlé.
- **AC-POL-007** Décision policy tracée avec motif (allow/deny + rule id).

## 4.3 Auth tests (OAuth / API key / auto)
Objectif: valider le resolver d’auth et la robustesse de cycle token.

- **AC-AUTH-001** Mode `api_key` avec clé valide → appel LLM autorisé.
- **AC-AUTH-002** Mode `api_key` invalide → erreur auth et pas de fallback implicite.
- **AC-AUTH-003** Mode `oauth` token valide → appel LLM autorisé au nom user.
- **AC-AUTH-004** Mode `oauth` token expiré + refresh OK → succès après refresh.
- **AC-AUTH-005** Mode `oauth` refresh KO → échec contrôlé, secret non exposé.
- **AC-AUTH-006** Mode `auto` avec user context valide → OAuth prioritaire.
- **AC-AUTH-007** Mode `auto` sans user context + policy autorise fallback → API key utilisée.
- **AC-AUTH-008** Mode `auto` sans user context + policy interdit fallback → refus explicite.
- **AC-AUTH-009** `auth_mode` correctement reporté dans `TraceEvent`.

## 4.4 MCP integration tests
Objectif: valider registry, ACL par agent, résilience et audit redacted.

- **AC-MCP-001** Serveur MCP enregistré + allowlist agent → appel autorisé.
- **AC-MCP-002** Serveur non allowlisté → refus policy avant exécution.
- **AC-MCP-003** ACL différente par environnement (dev/prod) respectée.
- **AC-MCP-004** Timeout MCP → retry borné puis erreur finale normalisée.
- **AC-MCP-005** Réponse MCP partielle/corrompue → gestion erreur robuste.
- **AC-MCP-006** Audit input/output avec redaction des secrets/PII.

## 4.5 Chaos tests (timeouts, retries)
Objectif: vérifier la fiabilité sous dégradation.

- **AC-CHAOS-001** Injection latence LLM > timeout → timeout appliqué + trace.
- **AC-CHAOS-002** Erreurs transitoires LLM (5xx) → retries bornés, backoff, puis succès/échec déterministe.
- **AC-CHAOS-003** Worker interrompu en milieu d’étape → reprise idempotente sans duplication d’effets.
- **AC-CHAOS-004** Queue saturée → maintien SLA dégradé contrôlé, pas de perte silencieuse.
- **AC-CHAOS-005** MCP intermittent → retries bornés sans boucle infinie.

## 4.6 Security tests
Objectif: couvrir menaces prioritaires définies pour V1.

- **AC-SEC-001 Prompt injection**: prompts malveillants n’altèrent pas policy/tool constraints.
- **AC-SEC-002 Command bypass**: contournements shell obfusqués restent bloqués.
- **AC-SEC-003 Secret leakage**: secrets jamais renvoyés en clair dans sorties/logs/traces.
- **AC-SEC-004 Redaction**: PII/secrets redacted dans audit MCP et observabilité.
- **AC-SEC-005 Token security**: refresh tokens chiffrés au repos et non journalisés.

## 5) Critères Go / No-Go

### 5.1 Seuils globaux de succès
- **Go** si:
  - 100% des tests critiques (Policy/Auth/Security) passent.
  - ≥ 95% de l’ensemble des cas d’acceptation passent.
  - 0 échec sur exigences “approval obligatoire” et “secret leakage”.
- **No-Go** si un test critique échoue ou si régression de contrat API non justifiée.

### 5.2 Seuils de latence
- `POST /v1/tasks` p95 < **400 ms** (hors exécution métier asynchrone).
- `GET /v1/tasks/{task_id}` p95 < **250 ms**.
- `GET /v1/traces/{task_id}` p95 < **300 ms**.
- Appel LLM gateway p95 < **2.5 s** (hors prompts > seuil documenté).
- Appels MCP p95 < **1.5 s**.

### 5.3 Seuils d’erreurs
- Taux d’erreur 5xx API < **1%** sur campagne nominale.
- Taux d’erreur non récupérée en retry LLM/MCP < **2%** (scénario chaos contrôlé).
- 0 “silent failure” (toute erreur doit générer trace + code d’erreur normalisé).

## 6) Exécution et reporting
- Campagne minimale: **100 tâches de validation** (mix nominal, policy, auth, chaos, sécurité).
- Rapport par suite:
  - pass/fail par cas,
  - distribution latence (p50/p95/p99),
  - erreurs par type,
  - couverture exigences.
- Livrables: rapport HTML/JSON + export métriques + traces corrélées.

## 7) Matrice de traçabilité (spec → tests)

| Exigence `docs/spec.md` | Tests minimum associés |
|---|---|
| 3.1 Créer/versionner agents | AC-API-001, AC-API-003, AC-API-004 |
| 3.2 Lancer tâches planner/executor/critic | AC-API-006, AC-API-009, AC-CHAOS-003 |
| 3.3 Exécuter outils avec policy checks | AC-POL-001..007, AC-SEC-002 |
| 3.4 Appeler Codex via gateway | AC-AUTH-001..009, AC-CHAOS-001..002 |
| 3.5 Support MCP allowlist par agent | AC-MCP-001..003 |
| 3.6 Journaliser traces/coûts/latences/policy | AC-API-013..014, AC-POL-007 |
| 4 Sécurité | AC-SEC-001..005 |
| 4 Fiabilité (retries/idempotence) | AC-CHAOS-002..003, AC-MCP-004 |
| 4 Observabilité | AC-API-013..014, AC-SEC-004 |
| 4 Scalabilité | AC-CHAOS-004 |
| 4 Gouvernance (approval humain) | AC-API-011..012, AC-POL-005 |
| 7 Modes d’auth + responsabilités gateway | AC-AUTH-001..009, AC-SEC-004 |
| 8 Règles policy engine | AC-POL-001..007 |
| 9 MCP registry/ACL/timeout-retry/audit | AC-MCP-001..006 |
| 10 API minimale | AC-API-001..018 |
| 11 Déploiement (dev compose) | prérequis section 2 + campagne section 6 |
| 12 Critères d’acceptation globaux | seuils section 5 + campagne section 6 |

## 8) Priorisation d’exécution (ordre recommandé)
1. **Smoke contrats API** (AC-API-001,006,009,013).
2. **Policy/Auth critiques** (AC-POL-005/006, AC-AUTH-004/008).
3. **Sécurité** (AC-SEC-001..005).
4. **MCP + Chaos** (AC-MCP-004..006, AC-CHAOS-001..005).
5. **Campagne 100 tâches + validation Go/No-Go**.
