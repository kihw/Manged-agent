# Design: Codex Runtime Supervise par Plateforme Locale

## 1. Objectif

Refonder l'architecture du projet pour que Codex devienne le runtime d'execution local principal, tandis que la plateforme locale devient la source de verite des orchestrations, la couche de supervision, le moteur de policy et la memoire durable d'execution.

L'objectif n'est pas de construire une plateforme qui execute les agents a la place de Codex. L'objectif est de publier des orchestrations, les charger automatiquement dans Codex, observer leur execution reelle, stocker les workflows generaux et rendre visibles les problemes potentiels dans un dashboard afin d'ameliorer les orchestrations, agents, tools et skills.

## 2. Contexte et changement de modele

Le modele precedent etait centre sur une plateforme locale qui orchestrait et executait les agents via ses propres workers. Ce modele est insuffisant pour le besoin reel du produit.

Le nouveau modele valide est le suivant:

- l'utilisateur installe des plugins, agents, skills et tools
- l'utilisateur lance Codex IDE, Codex CLI ou l'application officielle Windows
- Codex charge automatiquement les orchestrations publiees par la plateforme
- Codex execute localement les etapes de ces orchestrations
- la plateforme applique les policies, collecte les evenements, persiste les runs et alimente le dashboard

Ce changement de modele est fondamental. La plateforme n'est plus le worker runtime principal. Elle devient le control plane et la memoire du systeme. Codex devient le runtime d'execution utilisateur.

## 3. Positionnement officiel

- Platform = publish, govern, observe, persist
- Codex = load, execute, emit events

La plateforme:

- stocke les orchestrations, leurs versions et leur statut
- expose les orchestrations publiees aux clients Codex
- applique les policies avant certaines actions sensibles
- recoit et persiste les evenements d'execution
- alimente le dashboard et les vues d'analyse produit/ops

Codex:

- se connecte a la plateforme locale au demarrage
- charge automatiquement les orchestrations publiees
- execute localement les etapes reelles
- emet des evenements logiciels explicites vers la plateforme

## 4. Repartition des roles

### Qui decide

L'humain decide. Il choisit les agents, plugins, skills, tools et publie les orchestrations ainsi que les regles de policy via la plateforme.

### Qui orchestre

La plateforme orchestre au niveau controle. Elle versionne les orchestrations, decide lesquelles sont publiees, cree les identites de run, distribue les policies applicables et encadre le cycle de vie global.

### Qui execute

Codex execute localement. C'est lui qui fait tourner les etapes, appelle les tools, interagit avec le workspace et fait vivre les orchestrations dans l'IDE, le CLI ou l'application Windows.

### Qui observe

La plateforme observe via instrumentation logicielle explicite. Elle recoit les evenements emis par Codex, les erreurs, les transitions d'etat, les appels outils et les demandes d'approbation. Aucun mecanisme d'IA ne doit reconstruire ou deviner l'activite.

### Qui persiste

La plateforme persiste. Elle stocke les orchestrations, leurs versions, les runs, les taches, les evenements, les erreurs, les workflows recurrentes et les signaux necessaires au dashboard.

## 5. Principes de conception

### 5.1 Instrumentation purement logicielle

La collecte de donnees d'usage, d'erreurs et de workflows doit venir uniquement d'une instrumentation logicielle explicite dans Codex, les plugins, les skills et les tools. Aucun composant IA ne doit etre utilise pour reconstruire les workflows ou deduire les taches apres coup.

### 5.2 Source de verite centralisee

La plateforme est la seule source de verite des orchestrations. Codex ne maintient qu'un cache local de lecture pour le demarrage et le mode degrade.

### 5.3 Separation entre execution et supervision

Codex execute. La plateforme supervise, autorise, observe et memorise. La plateforme ne rejoue pas l'execution locale et Codex ne detient pas la verite globale sur l'etat du systeme.

### 5.4 Gouvernance selective

La plateforme pre-autorise uniquement certaines actions sensibles. Le reste de l'execution peut avancer avec simple emission d'evenements et persistance continue.

### 5.5 Tolerance aux pannes

Le systeme doit rester explicable en mode degrade. Si la plateforme disparait, Codex peut s'appuyer sur le cache d'orchestrations deja charge, mais il ne doit pas demarrer un nouveau run non tracable.

## 6. Flux d'execution cible

1. Au demarrage, Codex se connecte a la plateforme locale et s'enregistre legerement comme client local.
2. La plateforme attribue ou revalide une identite technique d'instance pour cette session.
3. Codex recupere automatiquement les orchestrations publiees et compatibles avec son contexte.
4. L'utilisateur choisit une orchestration dans Codex, ou Codex active automatiquement une orchestration associee au projet charge.
5. Avant execution, Codex demande a la plateforme de creer un run et les identifiants associes (`run_id`, `task_id`, version, policy profile).
6. Codex execute localement les etapes reelles: plugins, tools, skills, commandes et interactions de projet.
7. Pendant l'execution, Codex emet des evenements structures vers la plateforme.
8. Avant toute action sensible, Codex demande une decision de policy a la plateforme.
9. La plateforme persiste l'historique du run, des taches et des evenements en continu.
10. A la fin, le run reste consultable dans l'application avec son titre, son workflow, ses incidents, ses etapes et son statut final.

## 7. Composants et frontieres

### 7.1 Orchestration Registry

Stocke les orchestrations, leurs versions, leur statut de publication, leur compatibilite et leurs metadonnees. C'est la seule source de verite.

### 7.2 Codex Runtime Adapter

Composant cote Codex qui:

- charge automatiquement les orchestrations au demarrage
- maintient un cache local
- lance les runs
- emet les evenements vers la plateforme
- demande des decisions de policy pour les actions sensibles

### 7.3 Policy Decision Service

Service de plateforme qui repond `allow`, `deny` ou `require_approval` avant execution d'une action sensible.

### 7.4 Run Ledger

Journal structure de tout ce qui se passe pendant un run: creation, etapes, outils, erreurs, decisions policy et fin d'execution.

### 7.5 Task Memory Store

Stockage oriente dashboard qui memorise les taches, leurs titres, leurs workflows generaux, leurs incidents et leurs contextes d'execution.

### 7.6 Instance Registry

Registre des instances Codex locales. Il permet de distinguer plusieurs instances sur la meme machine avec des identites techniques separees.

### 7.7 Dashboard Backend

Couche de lecture et d'agregation qui expose l'etat des orchestrations, runs, erreurs, tools, skills et tendances d'usage.

## 8. Identite locale des instances Codex

Le systeme ne necessite pas d'authentification forte externe pour la V1. En revanche, il a besoin d'une identite technique locale par instance de Codex afin de distinguer plusieurs clients dans le dashboard.

Le modele retenu est un enregistrement local leger:

- lors du premier lien avec la plateforme, une instance Codex obtient une identite locale
- chaque lancement de Codex revalide ou renouvelle son contexte d'instance
- le dashboard peut distinguer plusieurs instances en parallele sur la meme machine
- chaque instance peut executer des orchestrations differentes et produire ses propres runs

Cette identite sert au routage, au suivi, a la correlation et au debug. Elle ne doit pas etre confondue avec un systeme d'authentification utilisateur distant.

## 9. Actions sensibles et pre-autorisation

Les actions suivantes sont sensibles des la V1 et doivent passer par une demande explicite de decision a la plateforme avant execution:

- ecriture ou modification de fichiers hors du workspace cible
- suppression ou deplacement massif de fichiers
- commandes shell destructrices
- operations `git push`
- acces reseau sortant
- installation de dependances ou execution de binaires non approuves

La plateforme doit pouvoir repondre:

- `allow`
- `deny`
- `require_approval`

Le principe est simple:

- si l'action n'est pas sensible, Codex execute puis emet les evenements
- si l'action est sensible, Codex attend une decision explicite avant execution

## 10. Mode degrade et disponibilite

### 10.1 Plateforme indisponible au demarrage

Codex peut charger les orchestrations deja presentes dans son cache local, mais il ne doit pas demarrer un nouveau run tracable tant que la plateforme n'est pas redevenue disponible.

### 10.2 Plateforme indisponible pendant un run

Si aucune action sensible n'est en cours, Codex peut continuer tres brievement avec une file locale tampon d'evenements, puis tenter une resynchronisation. Des qu'une pre-autorisation est necessaire, l'execution doit se bloquer tant que la plateforme ne repond pas.

### 10.3 Echec d'emission d'evenement

Les evenements doivent etre places dans une file locale avec horodatage, ordre et identifiant idempotent, puis renvoyes a la reconnexion.

### 10.4 Decision policy absente, expiree ou incoherente

L'action sensible est refusee par defaut. Aucun comportement implicite ne doit etre autorise.

## 11. Protocole minimal entre Codex et la plateforme

### 11.1 Sync Orchestrations

Au demarrage, Codex synchronise les orchestrations publiees, leurs versions, leur compatibilite et son etat d'instance local.

### 11.2 Start Run

Quand l'utilisateur lance une orchestration, Codex demande a la plateforme de creer le `run`, les `task_id` associes et le profil de policy applicable.

### 11.3 Emit Event

Pendant l'execution, Codex envoie des evenements structures:

- debut ou fin d'etape
- appel d'outil
- erreur
- changement d'etat
- heartbeat
- resultat technique

### 11.4 Preauthorize Action

Avant une action sensible, Codex envoie une requete de decision a la plateforme avec le contexte minimal necessaire: type d'action, cible, workspace, outil et metadonnees utiles.

### 11.5 Complete Run

A la fin, Codex clot explicitement le run avec un statut terminal et un resume technique court.

Le protocole doit etre deterministe, idempotent et comprehensible sans reconstruction intelligente.

## 12. Modele de donnees minimal

### 12.1 Orchestration

Definit ce que Codex peut charger au demarrage.

Champs cles:

- `orchestration_id`
- `name`
- `version`
- `status`
- `entrypoint`
- `required_tools`
- `required_skills`
- `policy_profile`
- `compatibility`
- `published_at`

### 12.2 CodexInstance

Represente une instance locale precise de Codex.

Champs cles:

- `instance_id`
- `machine_id`
- `client_kind` (`ide`, `cli`, `windows_app`)
- `workspace_path`
- `started_at`
- `last_seen_at`
- `capabilities`

### 12.3 Run

Represente une execution d'orchestration.

Champs cles:

- `run_id`
- `orchestration_id`
- `orchestration_version`
- `instance_id`
- `status`
- `started_at`
- `ended_at`
- `trigger`
- `workspace_path`

### 12.4 Task

Represente une unite suivie dans le dashboard, liee a un objectif utilisateur concret.

Champs cles:

- `task_id`
- `run_id`
- `title`
- `goal`
- `status`
- `current_step`
- `started_at`
- `ended_at`

### 12.5 RunEvent

Evenement brut emis par Codex ou par la plateforme.

Champs cles:

- `event_id`
- `run_id`
- `task_id`
- `source` (`codex`, `platform`, `tool`, `policy`)
- `type`
- `timestamp`
- `payload`

### 12.6 ToolExecution

Trace d'un appel d'outil concret.

Champs cles:

- `tool_execution_id`
- `run_id`
- `task_id`
- `tool_name`
- `status`
- `started_at`
- `ended_at`
- `input_summary`
- `output_summary`
- `error_summary`

### 12.7 PolicyDecision

Decision prise avant une action sensible.

Champs cles:

- `decision_id`
- `run_id`
- `task_id`
- `action_type`
- `decision`
- `reason`
- `timestamp`

### 12.8 WorkflowFingerprint

Empreinte deterministe d'un workflow recurrent observe.

Champs cles:

- `fingerprint_id`
- `title_pattern`
- `orchestration_id`
- `step_signature`
- `tool_signature`
- `occurrence_count`
- `last_seen_at`

Cette entite ne depend d'aucune IA. Elle sert a regrouper des workflows similaires a partir de signatures deterministes comme l'orchestration, la sequence d'etapes, les outils appeles et les categories d'erreurs.

## 13. Regles de persistance et de memorisation

La plateforme doit memoriser en continu:

- les orchestrations et leurs versions
- les instances Codex connues
- les runs et leurs statuts
- les taches et leurs titres
- les evenements de run
- les executions d'outils
- les decisions de policy
- les erreurs
- les workflows recurrentes et leurs signatures

Le but n'est pas l'analyse automatique par IA mais la capitalisation logicielle des faits d'execution pour pouvoir comprendre, tester et ameliorer le comportement reel des orchestrations.

## 14. Dashboard et usages attendus

Le dashboard doit permettre:

- de visualiser toutes les taches creees depuis Codex
- de distinguer plusieurs instances Codex sur la meme machine
- d'identifier les orchestrations les plus executees
- de voir les erreurs recurrentes par orchestration, tool, skill ou plugin
- de suivre les actions sensibles bloquees ou approuvees
- de retrouver les workflows generaux executes le plus souvent

Le dashboard est un outil produit et ops. Il sert a observer le rendu reel des orchestrations afin de les ameliorer.

## 15. Tests et criteres de succes V1

### 15.1 Tests de publication

Verifier qu'une orchestration publiee par la plateforme apparait automatiquement au demarrage de Codex avec la bonne version et le bon statut de compatibilite.

### 15.2 Tests d'execution

Verifier qu'un run lance depuis Codex cree bien cote plateforme les entites suivantes:

- `run`
- `task`
- `events`
- `tool executions`
- `policy decisions`
- statut terminal

### 15.3 Tests multi-instances

Lancer plusieurs instances Codex sur la meme machine avec des orchestrations differentes et verifier que le dashboard les distingue proprement.

### 15.4 Tests des actions sensibles

Verifier qu'aucune action sensible listée en V1 n'est executee sans pre-autorisation.

### 15.5 Tests du mode degrade

Verifier que:

- Codex peut lire le cache si la plateforme est absente
- aucun nouveau run non tracable n'est demarre
- une action sensible bloque immediatement si la plateforme est indisponible

### 15.6 Tests de persistance

Verifier que les taches restent consultables dans l'application avec leur titre, leur sequence generale, leurs erreurs, leurs outils utilises et leur historique complet.

### 15.7 Criteres d'acceptation V1

- une orchestration publiee dans la plateforme apparait automatiquement dans Codex au demarrage
- un run execute par Codex est visible quasi immediatement dans l'application
- plusieurs instances Codex locales sont distinguees correctement
- aucune action sensible n'est executee sans pre-autorisation
- aucune analyse IA n'est utilisee pour reconstruire les workflows ou les taches
- les workflows generaux sont regroupes de maniere deterministe et stockes durablement

## 16. Impacts sur l'architecture existante

L'architecture actuelle du projet devra evoluer dans les directions suivantes:

- deplacer le centre de gravite depuis un worker runtime plateforme vers un modele de supervision
- conserver les briques utiles de persistance, traces, policy et dashboard
- introduire une couche d'integration Codex capable de charger automatiquement les orchestrations
- remodeler l'API autour des notions de publication, sync, run, event et pre-autorisation
- distinguer clairement ce qui appartient a l'execution locale Codex et ce qui appartient au control plane de la plateforme

Le systeme n'est pas abandonne. Il est recadre. Les briques existantes restent utiles si elles sont repositionnees autour du nouveau role de la plateforme.

## 17. Hors scope V1

- authentification forte multi-utilisateur
- execution distante des etapes a la place de Codex
- reconstruction intelligente de workflows
- analyse IA des comportements
- orchestration distribuee multi-machines

## 18. Resume executif

La V1 cible n'est pas une plateforme qui execute les agents. C'est une plateforme locale qui publie les orchestrations, les expose automatiquement a Codex, supervise leur execution reelle, applique des garde-fous sur les actions sensibles et memorise durablement tout ce qui se passe afin d'ameliorer les orchestrations sur la base de faits logiciels explicites.
