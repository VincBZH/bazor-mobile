# BAZOR — réparer/tester les communications IA en un clic

**Statut :** candidat intégré, CI hors PC verte. **L'installation et le vrai test sur le PC Windows de Vincent restent à effectuer.**  
**Branche unique de validation :** `feat/airoom-v24-core-multiia-20260926` · [PR #169](https://github.com/VincBZH/bazor-mobile/pull/169).  
**Origine du correctif de transport Mammouth :** [PR #150](https://github.com/VincBZH/bazor-mobile/pull/150), désormais reprise dans #169, non fusionnée sur main.  
**Responsable de cette intégration :** GPT-5.6 Sol, session ChatGPT principale de Vincent ; je n'affirme pas avoir exécuté le lanceur sur son PC.

## Une seule action pour Vincent, dans Opera

1. Récupérer [l'archive de la branche intégrée](https://github.com/VincBZH/bazor-mobile/archive/refs/heads/feat/airoom-v24-core-multiia-20260926.zip), puis l'extraire dans **un NOUVEAU dossier**, pas par-dessus son BAZOR actuel.
2. Double-cliquer sur `BAZOR_REPARER_CONNEXIONS_1_CLIC.cmd`. Une fenêtre affiche les étapes et reste ouverte, y compris en cas d'erreur.
3. Si le contrôle local réussit, ouvrir **http://127.0.0.1:8768/** dans Opera. Les rapports et les journaux sont enregistrés dans `%LOCALAPPDATA%\BAZOR_ONECLICK`.

La case `--test-mammouth` déjà intégrée au lanceur **autorise un seul appel Mammouth plafonné et synthétique** (test « 2 + 2 ») **si** une clé est disponible et si le budget indiqué par BAZOR est suffisant. Aucun document privé n'est transmis. Ne pas lancer plusieurs fois de suite en cas d'erreur Mammouth. Si Vincent souhaite tester *uniquement* le local sans dépense, exécuter depuis le dossier extrait : `py -3 pc-relay\bazor_multiai_oneclick.py`.

## Ce que ce lanceur fait réellement

- Teste la syntaxe des fichiers Core, Mammouth, pont et Room avant de lancer quoi que ce soit.
- Réutilise Ollama en local et privilégie `llama3.2:3b`, puis `qwen2.5-coder:7b` ; refuse de sélectionner automatiquement un modèle 32b/70b trop lourd. Si Ollama n'est pas actif, tente de le démarrer **seulement** si la CLI est installée et que le port 11434 est libre. Ne télécharge ni ne supprime aucun modèle.
- Réutilise un Core actif **uniquement après vérification exacte de sa signature et de son identité**. Sinon démarre un Core *isolé* sur **127.0.0.1:8875**, sans découverte UDP, avec ses propres données dans `BAZOR_ONECLICK`. Il n'arrête pas ni n'écrase l'ancien Core 8775.
- Démarre ou vérifie la véritable Room V2.4 sur **127.0.0.1:8768**, rattachée au Core identifié, avec le modèle léger choisi. Refuse un port occupé par une application inconnue.
- Exécute un **vrai aller-retour Room → Core → Ollama** avec un message de test constant. Un HTTP 200, l'existence d'un processus ou la présence d'une clé **ne constituent jamais seuls une preuve de succès**.
- Si Mammouth est autorisé et configuré, exécute le contrôle borné Ollama → Mammouth → Ollama, avec **une seule requête Mammouth**, le profil `light`, identité réelle des modèles, provenance des trois étapes et marqueur exact `BAZOR_BRIDGE_E2E_OK`. La preuve est conservée dans `bridge_runtime_proof.json`.
- Si la GitHub CLI `gh` est installée et connectée, peut répondre à **l'unique ticket de contrôle public autorisé [#168](https://github.com/VincBZH/bazor-mobile/issues/168)**, rédigé par le propriétaire du dépôt, avec un nouvel aller-retour réel de test depuis Ollama ; ne lit/exécute aucune commande issue d'un ticket. Cette étape vérifie GitHub comme *transport* ; elle **ne constitue pas une API GPT directe**. Si `gh` est absente ou non authentifiée, le statut reste EN ATTENTE.
- La connexion GPT/Astra directe reste **manuelle**, NoTrack reste désactivé tant que l'API/autorisation n'est pas validée. DuckDuckGo/Tor servent éventuellement à la recherche/navigation, pas à simuler un fournisseur de modèle IA. Ollama et ses ports ne sont pas exposés sur Internet.

## Rapport lisible, sans faux voyants verts

Le JSON `rapport_YYYYMMDD_HHMMSS.json` indique pour chaque couche `PASS_REAL_LOCAL`, `PASS_REAL_BRIDGE`, `PENDING` ou `BLOCKED` avec la cause. Les fichiers `isolated_core.log`, `isolated_room.log` et éventuellement `ollama.log` aident à corriger les erreurs. **Ne pas joindre aux issues publiques un fichier qui pourrait contenir des données confidentielles, un chemin personnel ou un secret.** Le rapport JSON écarte les clés et les textes de conversations.

**Retour arrière :** le lanceur n'écrase aucun fichier de la version actuellement installée. Les deux instances de test sont identifiées par les ports **8875** et **8768**, et restent distinctes des services historiques. Pour arrêter le test, identifier leurs PID via le Moniteur de ressources Windows / l'onglet Détails du Gestionnaire des tâches, vérifier qu'il s'agit des instances situées dans la copie extraite, puis les arrêter. **Ne pas fermer au hasard d'autres processus Python, ComfyUI ou Ollama.** Supprimer ensuite uniquement le dossier de test extrait si désiré, en conservant le rapport si besoin.

## Preuves déjà disponibles — et limites

- [CI intégration pont + un clic](https://github.com/VincBZH/bazor-mobile/actions/workflows/bazor-multiia-oneclick-ci.yml) : syntaxe Python/JavaScript, tests unitaires de sécurité du lanceur, **24 tests du pont** (dont véritable exécutable `curl` vers un serveur Mammouth *simulé*), **10 tests HTTP Room → Core simulé**, contrôle statique du lanceur ; **aucun crédit Mammouth utilisé dans cette CI**.
- [CI Room V2.4](https://github.com/VincBZH/bazor-mobile/actions/workflows/bazor-room-core-relay-ci.yml) : deuxième série distincte de vérifications hors PC.
- [#151](https://github.com/VincBZH/bazor-mobile/issues/151) : reste la référence des preuves runtime réelles exigées avant fusion. [#168](https://github.com/VincBZH/bazor-mobile/issues/168) : transport GPT/GitHub/watcher à certifier.
- **Non établi dans ce compte rendu :** test sur le PC de Vincent, présence actuelle de sa clé Mammouth, comportement du vrai fournisseur au moment du test, disponibilité du watcher local, disponibilité d'une API GPT ou NoTrack. Un code prêt et des tests simulés verts ne signifient **pas** que les quatre IA sont automatiquement reliées.

Une fois le rapport Windows obtenu, les erreurs concrètes doivent être corrigées sur **cette même branche et dans cette même PR**, sans créer un autre routeur. Ne fusionner vers `main` qu'après validation des services réels et du retour dans Opera.
