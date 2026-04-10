# Managed Agent V1 Platform

Plateforme locale Windows pour publier des orchestrations, laisser Codex les executer localement, superviser les runs, appliquer les policies sur actions sensibles et alimenter un dashboard sans analyse IA implicite.

## Produit Windows autonome

- Livrable cible: `Managed Agent.exe` lance en GUI, demarre le serveur local et ouvre le dashboard.
- Persistance par defaut: SQLite locale dans `%LocalAppData%\Managed Agent\data\`.
- Reseau par defaut: `127.0.0.1` uniquement.
- Mode LAN optionnel: `--allow-lan --admin-secret <secret>` pour exposer API + dashboard sur le reseau local.
- Build release Windows: `pwsh -File .\scripts\build_windows_release.ps1`.

Documentation d'exploitation Windows: `docs/windows-operations.md`

## Ce que contient ce repo

- API FastAPI V1 autour de `orchestrations`, `instances`, `runs`, `events`, `policy` et `dashboard`
- Lanceur desktop Windows dans `managed_agent.py`
- Adaptateur Codex de reference en Python dans `codex_adapter/`
- Dashboard web V1 servi par FastAPI
- Packaging Windows dans `ops/windows/` et `scripts/build_windows_release.ps1`

## Developpement local

1. Installer les dependances Python:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Copier les variables d'environnement Windows si besoin:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Lancer le serveur API local:

   ```powershell
   uvicorn app.main:app --reload --port 8080
   ```

4. Ouvrir le dashboard:

   ```text
   http://localhost:8080/dashboard
   ```

## Docker Compose

Pour lancer un runtime dev PostgreSQL explicite:

```powershell
docker compose up --build
```

Services exposes:

- Dashboard/API: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

Le mode Docker n'est pas le chemin nominal du produit Windows distribue.

## API V1

Endpoints principaux:

- `POST /v1/instances/register`
- `GET /v1/orchestrations/sync`
- `POST /v1/orchestrations`
- `POST /v1/runs`
- `POST /v1/runs/{run_id}/events:batch`
- `POST /v1/policy/preauthorize`
- `POST /v1/runs/{run_id}/complete`
- `GET /v1/dashboard/overview`
- `GET /v1/dashboard/workflows`
- `GET /v1/dashboard/workflows/{fingerprint_id}`
- `GET /v1/dashboard/errors`
- `GET /v1/dashboard/errors/{category}`
- `GET /v1/dashboard/runs/{run_id}`

Dashboard HTML pages:
- `/dashboard`
- `/dashboard/runs`
- `/dashboard/instances`
- `/dashboard/orchestrations`
- `/dashboard/workflows`
- `/dashboard/errors`

Le header `X-Instance-Token` est requis pour les appels provenant d'une instance Codex deja enregistree.

## Adaptateur Codex de reference

`codex_adapter/client.py` fournit un client local de reference pour:

- enregistrer une instance Codex
- synchroniser les orchestrations publiees
- demarrer un run
- emettre des evenements de run
- demander une pre-autorisation
- terminer un run

Le cache local utilise:

- `.data/codex-adapter/instance.json`
- `.data/codex-adapter/orchestrations-cache.json`
- `.data/codex-adapter/outbox.jsonl`

En mode offline, l'adaptateur peut lire le cache d'orchestrations, mais il refuse de demarrer un nouveau run et bloque toute action sensible faute de pre-autorisation.

## Migrations PostgreSQL

Pour initialiser une base PostgreSQL V1:

```powershell
python scripts/migrate_postgres.py
```

## Smoke test de reference

Le script:

```powershell
python scripts/smoke_test_v1.py --base-url http://localhost:8080
```

publie une orchestration, enregistre une instance, synchronise les orchestrations, cree un run, emet des evenements, declenche une policy `require_approval`, la resolut, puis cloture le run.

Smoke test du binaire Windows packagé:

```powershell
python scripts/smoke_test_windows_release.py --exe .\dist\Managed Agent\Managed Agent.exe
```

## Tests

Executer la suite:

```powershell
python -m pytest -q
```

La suite couvre:

- les modeles de domaine V1
- les endpoints plateforme
- le contrat OpenAPI publie
- l'adaptateur Codex de reference

## Documentation cle

- spec validee: `docs/superpowers/specs/2026-04-09-codex-supervised-runtime-design.md`
- note de transition: `docs/spec.md`
- exploitation Windows: `docs/windows-operations.md`
