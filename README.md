# Managed Agent — Local Control Plane

Plateforme locale pour orchestrer des agents managés avec gateway LLM (Codex), policy engine, exécution d’outils sandboxés et observabilité.

## Prérequis

- Docker et Docker Compose v2
- Git
- (Optionnel) Python 3.12+ pour validations locales sans conteneur

## Démarrage local

1. Cloner le dépôt.
2. Copier les variables d’environnement :

   ```bash
   cp .env.example .env
   ```

3. Renseigner au minimum `CODEX_API_KEY` dans `.env`.
4. Démarrer la stack :

   ```bash
   docker compose up -d
   ```

5. Vérifier l’état :

   ```bash
   docker compose ps
   ```

Services exposés par défaut :

- API: http://localhost:8080
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Loki: http://localhost:3100
- Postgres: localhost:5432
- Redis: localhost:6379
- Qdrant: localhost:6333

## Variables d’environnement

Voir `.env.example` pour la liste complète.

Variables principales :

- `APP_ENV` : environnement applicatif (`dev` par défaut)
- `DATABASE_URL` : connexion PostgreSQL
- `REDIS_URL` : connexion Redis
- `CODEX_AUTH_MODE` : `auto`, `api_key` ou `oauth`
- `CODEX_API_BASE_URL` : URL de base API Codex/OpenAI
- `CODEX_API_KEY` : clé API (requise en mode `api_key` ou fallback `auto`)
- `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` : credentials OAuth
- `OAUTH_REDIRECT_URI` : callback OAuth local
- `OAUTH_TOKEN_URL` / `OAUTH_AUTH_URL` : endpoints provider OAuth
- `OTEL_EXPORTER_OTLP_ENDPOINT` : endpoint collector OpenTelemetry

## Commandes de base

### Démarrer / arrêter

```bash
docker compose up -d
docker compose down
```

### Logs

```bash
docker compose logs -f api
docker compose logs -f worker
```

### Validation OpenAPI et schémas JSON (local)

```bash
python -m pip install -q openapi-spec-validator check-jsonschema
openapi-spec-validator openapi.yaml
check-jsonschema --schemafile agent.schema.json agent.schema.json
check-jsonschema --schemafile policy.schema.json policy.schema.json
```

### Exécuter les validations CI localement

```bash
python -m pip install -q yamllint
yamllint .
python -m json.tool agent.schema.json >/dev/null
python -m json.tool policy.schema.json >/dev/null
```

## Rebuild images

Les dépendances Python sont maintenant installées à la build des images `api` et `worker`.

```bash
docker compose build api worker
docker compose up -d
```

Pour forcer une reconstruction sans cache :

```bash
docker compose build --no-cache api worker
```

## Update dependencies

1. Mettre à jour les versions pinées dans `requirements.txt`.
2. Rebuilder les images pour appliquer les changements.

```bash
docker compose build api worker
```

3. Redémarrer les services.

```bash
docker compose up -d api worker
```

