# Contributing

## Conventions de code

### Format

- **Python**: formatage avec `black` (line-length 100).
- **Imports Python**: tri avec `isort` (profil `black`).
- **YAML**: validation et style via `yamllint`.
- **JSON**: documents et schémas doivent être valides (`python -m json.tool`).
- **Markdown**: lint via `markdownlint-cli`.

### Lint

- **Python**: lint statique avec `ruff`.
- **YAML/JSON/Markdown**: lintés en CI via workflow `ci.yml`.
- Toute PR doit passer les jobs CI avant merge.

### Typing

- Nouveau code Python: annotations de type obligatoires sur les fonctions publiques.
- Validation statique recommandée avec `mypy` (mode strict progressif).
- Éviter `Any` sans justification documentée.

## Workflow recommandé local

```bash
# Python quality tools (si du code Python est modifié)
python -m pip install -q black isort ruff mypy
black .
isort .
ruff check .
mypy .

# Contrats et docs
python -m pip install -q openapi-spec-validator check-jsonschema yamllint
openapi-spec-validator openapi.yaml
check-jsonschema --schemafile agent.schema.json agent.schema.json
check-jsonschema --schemafile policy.schema.json policy.schema.json
yamllint .
python -m json.tool agent.schema.json >/dev/null
python -m json.tool policy.schema.json >/dev/null
```
