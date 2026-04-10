# Exploitation Windows

## Emplacements par defaut

- Binaire installe: `%LocalAppData%\Programs\Managed Agent\`
- Base SQLite: `%LocalAppData%\Managed Agent\data\managed-agent-v1.db`
- Cache/runtime: `%LocalAppData%\Managed Agent\cache\`
- Logs: `%LocalAppData%\Managed Agent\logs\managed-agent.log`
- Config locale: `%LocalAppData%\Managed Agent\config\`

## Lancement

- Double-clic sur `Managed Agent` demarre le serveur local en arriere-plan puis ouvre le dashboard.
- Le service ecoute `127.0.0.1` par defaut.
- Si `8080` est deja pris, le launcher choisit automatiquement un port libre.

## Mode LAN optionnel

- Activer le LAN avec `Managed Agent.exe --allow-lan --admin-secret <secret>`.
- Sans `--admin-secret`, le launcher refuse le demarrage.
- En mode LAN, le dashboard et l'API demandent le secret admin.
- Les appels API peuvent fournir `X-Admin-Secret`.
- Le navigateur local est amorce avec un cookie via `?admin_secret=<secret>`.

## Reset local

- Arreter le processus `Managed Agent.exe`.
- Supprimer `%LocalAppData%\Managed Agent\cache\desktop-state.json` si le launcher pense qu'une ancienne instance tourne encore.
- Supprimer la base SQLite dans `%LocalAppData%\Managed Agent\data\` pour repartir de zero.

## Upgrade manuel

- Installer une nouvelle version par-dessus l'ancienne.
- Les binaires dans `%LocalAppData%\Programs\Managed Agent\` sont remplaces.
- Les donnees utilisateur sous `%LocalAppData%\Managed Agent\` sont conservees.

## Build release

```powershell
pwsh -File .\scripts\build_windows_release.ps1
```

Dependances externes:

- Python 3.12+ disponible dans le `PATH`
- Inno Setup 6 pour generer l'installateur
- Optionnel: `SIGNTOOL_EXE`, `WINDOWS_SIGN_CERT_FILE`, `WINDOWS_SIGN_CERT_PASSWORD` pour signer le binaire et l'installateur
