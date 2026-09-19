# BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth

## Nom officiel
**BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth**

But: un cockpit unique où Vincent parle une seule fois. Room distribue, mémorise, classe et journalise les échanges entre GPT, Ollama et Mammouth sans copier-coller humain.

## 1. Identité stricte des agents
Chaque message interne doit contenir un `agent_id` stable. Un agent ne doit jamais se présenter comme un autre.

- `gpt` — Nom affiché: **GPT** — coordinateur, synthèse, arbitrage, validation de preuve. Interdit de prétendre être Mammouth ou Ollama.
- `ollama` — Nom affiché: **Ollama local** — lecture locale autorisée, code, tâches répétitives, contrôles techniques, économie de crédits. Interdit de contourner Action Engine, d’exécuter du shell reçu depuis GitHub, ou de déclarer DONE sans preuve.
- `mammouth` — Nom affiché: **Mammouth** — seconde lecture externe indépendante, critique, comparaison de modèles/profils, avis de cohérence. Interdit de se présenter comme GPT/Ollama, d’écrire directement dans les fichiers critiques, ou de déclarer un runtime prouvé sans preuve.
- `bazor_core` — Nom affiché: **BAZOR Core** — routage, sécurité, mémoire, journalisation, FileBus, Action Engine, état réel des capacités.

## 2. Handshake obligatoire au début d'une journée ou d'une nouvelle conversation
Avant de répondre à Vincent, Room exécute un bootstrap de contexte:
1. charger `context/IDENTITIES.json`;
2. charger `context/CURRENT_STATE.json`;
3. charger `BAZOR_ENCYCLOPEDIA.md`;
4. charger `bazor_registry.json`;
5. charger le résumé du projet/conversation courant;
6. charger les derniers handoffs utiles du FileBus;
7. vérifier les capacités réelles: GPT, Ollama, Mammouth, Core, FileBus;
8. consigner un court `CONTEXT_BOOTSTRAP_OK` avec date, versions et sources lues.
Si une source manque ou est périmée, l'agent doit le dire et ne pas inventer.

## 3. Mémoire locale et contexte
Room doit conserver une mémoire locale structurée. Ce n'est pas un réentraînement automatique des modèles; c'est une base de contexte réutilisée à chaque échange.

Structure recommandée:
- `context/IDENTITIES.json` : identité/rôle/règles immuables des agents.
- `context/CURRENT_STATE.json` : état courant des services, versions, blocages.
- `context/projects/<project_id>/SUMMARY.md` : résumé vivant du projet.
- `context/projects/<project_id>/DECISIONS.jsonl` : décisions et raisons.
- `context/projects/<project_id>/FACTS.jsonl` : faits vérifiés et provenance.
- `context/projects/<project_id>/OPEN_TASKS.json` : tâches ouvertes + dépendances.
- `context/conversations/<conversation_id>.jsonl` : conversation locale brute.
- `context/conversations/<conversation_id>.summary.md` : résumé compact.
- `context/index.json` : index tags/projets/dates/agents.
- `context/daily/YYYY-MM-DD.md` : synthèse quotidienne des changements.

## 4. Classement automatique des conversations
Chaque message/conversation reçoit `conversation_id`, `project_id`, `tags`, `agent_id`, `timestamp`, `source`, `confidence`, `evidence_refs` et `status` (`info`, `decision`, `task`, `proof`, `blocked`, `done`).
Room doit permettre recherche plein texte + filtres par projet, agent, tag, date, statut.

## 5. Apprentissage contextuel
À la fin d'une conversation ou lorsqu'une décision importante est validée:
1. résumer les faits nouveaux;
2. séparer faits, hypothèses, décisions et préférences;
3. écrire seulement les faits utiles et non sensibles dans la mémoire locale;
4. lier chaque entrée à sa source;
5. mettre à jour le résumé du projet;
6. ne jamais écraser l'historique brut;
7. ne jamais convertir une simple réponse IA en fait vérifié sans preuve.

## 6. Synchronisation Encyclopédie + Registry
À chaque nouveau build/patch/version BAZOR:
- mettre à jour `BAZOR_ENCYCLOPEDIA.md`;
- mettre à jour `bazor_registry.json`;
- enregistrer version/build/date, fichiers changés, tests exécutés, preuves runtime, rollback/backup, limitations connues et prochaine étape.
Le build est incomplet si Encyclopédie et Registry ne sont pas synchronisés.

## 7. Communication automatique
Canal logique: **Vincent -> AI Room -> BAZOR Core -> GPT / Ollama / Mammouth -> AI Room**.
GitHub/FileBus reste le bus durable pour handoffs et preuves, pas un terminal distant.

Règles:
- aucun copier-coller humain entre IA;
- les handoffs sont publiés automatiquement;
- `agent_id` obligatoire;
- source et modèle réel doivent être affichés;
- un échec provider déclenche fallback contrôlé;
- aucun faux PASS;
- si Mammouth/Ollama/GPT est indisponible, Room affiche `INDISPONIBLE` au lieu de simuler sa présence.

## 8. Vue UI minimale
En-tête: **BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth**
Panneaux: Vincent / GPT / Ollama local / Mammouth / Système-BAZOR.
Indicateurs permanents: connecté-indisponible-limité, modèle réel, tâche courante, projet, contexte chargé, dernière synchro Encyclopédie, dernière synchro Registry, FileBus, dernière preuve runtime.

## 9. Règle d'identité anti-confusion
Avant chaque réponse d'un agent: lire son `agent_id`, vérifier que le nom affiché correspond, ajouter la provenance interne, refuser toute auto-présentation contradictoire.
Exemples: GPT ne dit jamais « je suis Mammouth ». Mammouth ne dit jamais « je suis GPT ». Ollama ne parle jamais au nom de GPT/Mammouth. BAZOR Core orchestre et rapporte.

## 10. Critère de réussite
La Room est considérée opérationnelle lorsque:
- une consigne unique de Vincent est distribuée à au moins deux moteurs;
- chaque moteur répond avec son identité correcte;
- la réponse est visible dans Room sans copier-coller;
- le contexte de projet est rechargé au nouveau chat;
- une décision validée est retrouvable le lendemain;
- Encyclopédie + Registry sont synchronisés au build;
- les preuves runtime sont conservées.