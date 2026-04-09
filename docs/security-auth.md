# Sécurité d’authentification et gouvernance des secrets

## 1) Flux OAuth 2.1 — Authorization Code + PKCE

### Objectif
Mettre en place une authentification utilisateur robuste pour l’accès au LLM Gateway, sans exposer de secret client côté front-end.

### Séquence recommandée
1. Le client génère un `code_verifier` cryptographiquement aléatoire (43–128 chars) et dérive un `code_challenge` via `S256`.
2. Le client redirige l’utilisateur vers l’Authorization Server avec:
   - `response_type=code`
   - `client_id`
   - `redirect_uri`
   - `scope` (least privilege)
   - `state` (anti-CSRF)
   - `code_challenge` + `code_challenge_method=S256`
3. Après consentement, l’Authorization Server renvoie `code` + `state` au `redirect_uri`.
4. Le backend échange `code` contre `access_token` + `refresh_token` via `code_verifier`.
5. Le backend valide:
   - correspondance `state`
   - `iss`, `aud`, `exp`, `iat`, `nonce` (si OIDC)
   - scopes attendus
6. Les tokens sont stockés côté serveur uniquement (jamais en localStorage / sessionStorage).

### Exigences de sécurité
- PKCE obligatoire (`S256`), `plain` interdit.
- Durée de vie courte pour `access_token` (ex. 5–15 min).
- Rotation active des `refresh_token` (voir section 2).
- Ré-authentification forcée en cas de suspicion (anomalie IP/device/risk score).

---

## 2) Stockage chiffré des refresh tokens

### Principes
- Les `refresh_token` sont chiffrés au repos avec une clé gérée par KMS/secret manager.
- Le chiffrement est **envelope encryption**:
  - DEK (data encryption key) par enregistrement/session.
  - DEK chiffrée par une KEK maîtresse (KMS).
- Séparer strictement:
  - métadonnées token (user_id, provider, issued_at, expires_at, scope hash)
  - matériel secret chiffré (ciphertext + nonce + tag).

### Contrôles minimaux
- AES-256-GCM (ou équivalent AEAD validé) pour confidentialité + intégrité.
- Clés en rotation périodique (KEK) et rewrap asynchrone des DEK.
- Accès au déchiffrement restreint au service d’auth.
- Journalisation d’accès aux secrets (qui/quand/pourquoi).

### Bonnes pratiques opérationnelles
- Jamais de token en clair dans logs, traces, dumps mémoire exportés.
- Suppression immédiate (hard delete logique + purge) à révocation utilisateur.
- TTL de conservation des tokens inactifs (ex. 30–90 jours).

---

## 3) Stratégie de rotation / révocation des API keys

### Rotation
- Dual-key strategy: chaque principal dispose d’une clé active + une clé de transition.
- Rotation planifiée (ex. toutes les 30/60/90 jours selon criticité).
- Déploiement en 3 phases:
  1. **Create**: générer nouvelle clé en secret manager.
  2. **Cutover**: services lisent la nouvelle clé, ancienne encore acceptée (fenêtre courte).
  3. **Revoke**: suppression définitive de l’ancienne clé.

### Révocation
- Révocation immédiate sur incident (fuite, usage anormal, départ collaborateur).
- Liste de révocation propagée en temps quasi-réel à tous les validateurs.
- Invalidation des sessions dérivées de la clé compromise.

### Gouvernance
- Interdiction de clés partagées entre environnements (dev/staging/prod).
- Scope minimal par clé (principle of least privilege).
- Ownership explicite (owner technique + métier) et date d’expiration obligatoire.

---

## 4) Matrice de fallback `oauth -> api_key` par policy profile

Règle générale: fallback autorisé **uniquement** si explicitement activé par le profil de policy.

| Policy profile | Mode primaire | Fallback `oauth -> api_key` | Conditions | Exigence d’audit |
|---|---|---|---|---|
| `strict` | `oauth` | **Interdit** | N/A | Log échec auth + refus explicite |
| `regulated` | `oauth` | **Interdit** (par défaut) | Exception temporaire via feature flag approuvé sécurité | Log + ticket d’exception + TTL |
| `balanced` | `oauth` | **Autorisé conditionnel** | OAuth indisponible, policy allowlist, pas d’action sensible | Log fallback + raison + durée |
| `developer` | `oauth` | **Autorisé** | Environnements non-prod uniquement | Log fallback standard |
| `breakglass` | `oauth` | **Autorisé forcé** | Incident majeur déclaré, approbation on-call + sécurité | Log renforcé + postmortem requis |

### Garde-fous fallback
- Backoff et circuit-breaker pour éviter bascules oscillantes.
- Durée de fallback bornée (ex. 15 min renouvelable avec approbation).
- Blocage automatique des actions sensibles en mode fallback, sauf `breakglass`.

---

## 5) Redaction stricte secrets/PII avant envoi au LLM

### Politique de redaction
- Toute donnée envoyée au LLM passe par un pipeline de sanitization obligatoire.
- Modèle “deny by default” pour champs sensibles non explicitement allowlistés.

### Catégories à redacter
- Secrets techniques: API keys, tokens OAuth/JWT, mots de passe, certificats, clés privées, DSN.
- Données d’infrastructure: IP internes, hostnames privés, chemins sensibles.
- PII: email, téléphone, adresse, identifiants nationaux, IBAN, données RH.
- Données réglementées métier (ex. santé, paiement) selon classification interne.

### Mécanismes
- Détection hybride:
  - regex haute précision (patterns connus),
  - classifieur PII,
  - règles contextuelles (nom de champ, schéma JSON, labels de classification).
- Redaction structurée avec placeholders stables:
  - `{{REDACTED_API_KEY}}`, `{{REDACTED_EMAIL}}`, etc.
- Hachage salé facultatif pour corrélation sans révélation (`HMAC(value, key_rotating)`).

### Exigences d’implémentation
- Redaction appliquée aux prompts, tool inputs/outputs, logs applicatifs et traces.
- Tests unitaires de non-régression sur corpus de secrets.
- “Fail closed”: en cas d’erreur de redaction, l’appel LLM est refusé.

---

## 6) Événements d’audit sécurité

### Événements obligatoires
1. `auth.login.success`
2. `auth.login.failure`
3. `auth.oauth.refresh.success`
4. `auth.oauth.refresh.failure`
5. `auth.api_key.revoke`
6. `auth.fallback.oauth_to_api_key`

### Schéma minimal commun
- `event_id`, `event_type`, `timestamp_utc`
- `actor_type` (`user`, `service`, `system`), `actor_id` pseudonymisé
- `tenant_id`, `environment`, `policy_profile`
- `request_id`, `trace_id`, `session_id`
- `result` (`success`/`failure`), `reason_code`
- `risk_level` (`low`/`medium`/`high`)
- `metadata_redacted` (objet JSON déjà redacted)

### Exigences de conformité
- Horodatage UTC synchronisé (NTP), immutabilité des journaux.
- Conservation selon politique légale (ex. 90j chaud + 1 an archive).
- Accès en lecture restreint (RBAC + traçabilité des consultations).

---

## 7) Checklist de durcissement

### Transport et réseau
- [ ] TLS interne obligatoire (mTLS recommandé entre services critiques).
- [ ] Cipher suites modernes, TLS 1.2+ minimum (1.3 recommandé).
- [ ] Segmentation réseau: auth/gateway isolés des workloads non fiables.

### Secrets et clés
- [ ] Secret manager/KMS central (pas de secrets en fichiers statiques).
- [ ] Rotation automatique des clés (API, DB, chiffrement).
- [ ] Détection de fuite de secrets dans CI/CD et dépôts Git.

### Identité et autorisations
- [ ] Scopes OAuth en least privilege.
- [ ] RBAC strict service-to-service + comptes techniques dédiés.
- [ ] Revue trimestrielle des permissions et suppression des accès dormants.

### Observabilité et réponse incident
- [ ] Alertes sur échecs login/refresh, pics de fallback, révocations massives.
- [ ] Dashboards sécurité (taux d’échec auth, latence token, events à risque).
- [ ] Runbook incident auth (containment, rotation, communication, postmortem).

### Plateforme
- [ ] Images durcies et patch management régulier.
- [ ] Policies runtime (seccomp/AppArmor/SELinux selon stack).
- [ ] Sauvegardes chiffrées, testées, avec restauration périodique.
