# Transition note: Managed Agent V1

Ce fichier remplace l'ancienne specification centree sur `agents/tasks/traces + worker + redis + oauth`.

Le modele officiel du repo est maintenant:

- la plateforme stocke les orchestrations et leurs versions
- Codex charge automatiquement ces orchestrations
- Codex execute localement les etapes
- la plateforme supervise, persiste, pre-autorise les actions sensibles et alimente le dashboard

Contrats publics V1:

- `instances/register`
- `orchestrations/sync`
- `runs`
- `runs/{run_id}/events:batch`
- `policy/preauthorize`
- `policy-decisions/{decision_id}/resolve`
- `dashboard/*`

Le document de reference produit reste:

- `docs/superpowers/specs/2026-04-09-codex-supervised-runtime-design.md`
