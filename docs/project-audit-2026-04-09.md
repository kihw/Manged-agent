# Audit de cohérence du projet (2026-04-09)

## Méthode
- Lecture des contrats et docs: `README.md`, `docs/spec.md`, `docs/data-model.md`, `docs/test-plan.md`, `openapi.yaml`.
- Revue du code exécutable: `app/main.py`, `app/routers/*`, `app/services/*`, `worker.py`.
- Vérifications locales: compilation Python (`python -m compileall`) et tentative de validation OpenAPI/JSON Schema.

## Constats majeurs

### 1) Contrat API implémenté vs spécification: écart important
**Observation**
- La spec produit une API minimale avec `POST /v1/agents`, `POST /v1/tasks`, `POST /v1/tasks/{task_id}/approve`, `POST /v1/auth/oauth/callback`.
- Le code expose uniquement des routes `GET` placeholder pour agents/tasks/traces et `GET /v1/auth/status`.

**Impact**
- Le backend n'implémente pas les parcours critiques décrits dans la spec (création d’agent, création/approbation de tâche, callback OAuth).
- Incompatibilité immédiate entre consommateurs API et service réel.

### 2) OpenAPI détaillé vs services Python: modèles incompatibles
**Observation**
- `openapi.yaml` décrit des schémas riches (`AgentTask`, `ApprovalRequest`, `TraceEvent`, etc.).
- Les protocoles Python (`app/services/*.py`) ne portent qu’un sous-ensemble minimal de champs (ex. `AgentTask` réduit à `task_id`, `agent_id`, `goal`, `status`).

**Impact**
- Contrats internes insuffisants pour porter les réponses documentées.
- Risque élevé de dérive entre sérialisation HTTP, persistance et logique métier future.

### 3) Incohérence de type sur `allowed_mcp_servers`
**Observation**
- `agent.schema.json` définit `allowed_mcp_servers` comme `array[string]`.
- `openapi.yaml` le définit comme `array[McpServer]` (objets structurés).

**Impact**
- Un payload valide côté OpenAPI peut être invalide côté JSON Schema (et inversement).
- Risque de rejet en validation selon l’outil utilisé en CI/runtime.

### 4) Incohérence de statuts entre documents de référence
**Observation**
- `docs/spec.md` et `openapi.yaml` utilisent `completed` et `canceled`.
- `docs/data-model.md` emploie `succeeded` et `cancelled` pour plusieurs tables.

**Impact**
- Mapping ambigu des états entre API, base de données et worker.
- Complexifie les dashboards, requêtes SQL et règles de transition.

### 5) Statut d’approbation réutilise abusivement le statut de tâche
**Observation**
- `approval-request.schema.json` réutilise l’enum global `queued|running|waiting_approval|completed|failed|canceled`.
- Un objet d’approbation devrait plutôt avoir des statuts dédiés (`pending`, `approved`, `rejected`, `expired`), déjà présents dans `docs/data-model.md`.

**Impact**
- Sémantique confuse dans les traces et réponses API.
- Difficulté à exprimer un refus explicite ou une expiration d’approbation.

### 6) CI incomplète vis-à-vis des artefacts présents
**Observation**
- Le workflow CI valide `agent.schema.json` et `policy.schema.json` seulement.
- Le repo contient aussi `task-step.schema.json`, `tool-execution.schema.json`, `approval-request.schema.json`, `artifact.schema.json`, `mcp-server.schema.json`, mais ils ne sont pas validés en CI.

**Impact**
- Régression possible sur des schémas pourtant référencés par OpenAPI.
- Couverture de qualité contractuelle partielle.

### 7) Docker Compose non déterministe en exécution
**Observation**
- Services `api` et `worker` installent des dépendances à chaud via `pip install` au démarrage, sans lockfile ni versions pinées.

**Impact**
- Démarrages lents, dépendance réseau à runtime et non-reproductibilité des environnements.
- Risque de rupture soudaine suite à une mise à jour upstream.

### 8) Worker placeholder + dépendances non exploitées
**Observation**
- `worker.py` boucle indéfiniment sans consommer de message réel (`message=None` en dur).
- `docker-compose.yml` installe `rq`/`redis` pour le worker, mais le code n’utilise pas ces librairies.

**Impact**
- Coût opérationnel inutile (logs infinis) sans capacité métier.
- Donne une fausse impression de support queue/processing.

## Vérifications exécutées
- ✅ `python -m compileall -q app worker.py`
- ⚠️ `python -m pip -q install openapi-spec-validator check-jsonschema` (échec réseau/proxy dans cet environnement, donc validation OpenAPI/JSON Schema non exécutable ici)

## Recommandations prioritaires (ordre conseillé)
1. **Aligner le contrat source-of-truth**: décider si OpenAPI ou JSON Schema fait foi pour chaque ressource, puis harmoniser les définitions.
2. **Implémenter le minimum fonctionnel des endpoints de la section API minimale** avec modèles Pydantic partagés.
3. **Uniformiser les statuts** (anglais US recommandé: `completed`, `canceled`, etc.) sur API + schémas + docs data model.
4. **Séparer les statuts d’approbation des statuts de tâche** (ajouter enum dédiée).
5. **Étendre la CI** pour valider tous les schémas JSON présents et vérifier les `$ref` OpenAPI externes.
6. **Rendre l’exécution Docker reproductible** (requirements lockés + image applicative dédiée).
7. **Soit brancher réellement la queue worker, soit documenter explicitement que le worker est un stub non opérationnel.**
