# BAZOR ULTIMATE — V0 diagnostic local (livrable de développement)

**Référence :** BAZOR-ULTIMATE-V0-DIAG-20260926  
**Responsable du correctif :** GPT-5.6 Sol, conversation ChatGPT principale de Vincent.  
**Branche :** `feat/bazor-ultimate-diagnostic-v0-20260926`  
**Statut :** **implémentation et tests simulés ; pas d'installation ni de test graphique sur le PC de Vincent.** Ce travail prolonge le bilan documentaire [BAZOR au 26/09/2026 à 22 h 15](https://github.com/VincBZH/bazor-mobile/pull/164).

## Livré sur cette branche

1. `console-hub/bazor_diagnostics.py` : quatre sondes HTTP locales **GET uniquement** (Core 8775, AI Room 8765, liaison déclarative Room/Core, Ollama 11434). États VERT / JAUNE / ROUGE / GRIS. Évite les faux verts pour `ok=false`, les réponses mal formées, les modèles Ollama absents et une déclaration de liaison incompatible avec un contrôle indépendant.
2. `console-hub/bazor_ultimate_dashboard.py` : surcouche **du vrai Hub existant** (classe `UltimateHub(Hub)`) ; réutilise ses tableaux/logs et lui ajoute un panneau de voyants actualisés en arrière-plan. L'ancien tableau est explicitement étiqueté comme historique « port/processus ».
3. **Bouton volontaire « Tester la conversation LOCALE »** : seul point d'entrée pour un `POST /api/chat` qui interroge Ollama via la Room et inscrit un message `BAZOR_OK` dans l'historique local. Le rafraîchissement automatique **ne génère jamais** de réponse.
4. `tests/test_bazor_diagnostics.py` et `tests/test_ultimate_dashboard.py` : **23 tests simulés/statiques**, pas de requête réseau, pas de Tkinter affiché ni de fournisseur payant.
5. `.github/workflows/bazor-ultimate-v0-ci.yml` : syntaxe Python + tests sur chaque modification des fichiers concernés.

## Ce qui n'est PAS encore démontré

- Le démarrage graphique sur le PC Windows de Vincent.
- Le statut actuel des instances Core/Room/Ollama au moment de l'installation.
- Une conversation réelle réalisée **avec cette version** du tableau de bord.
- Le raccourci Bureau « BAZOR ULTIMATE » testé.
- Les boutons RÉPARER, le rollback réel, les liaisons API Mammouth/GPT/Astra.
- La synchronisation du Hub présent sur le PC avec le clone GitHub : si son Hub local est différent de la version GitHub, une inspection est nécessaire avant installation.

## Points d'attention de sécurité

- **Ne jamais lancer** `console-hub/bazor_start_hub.ps1` ni le Hub avec `--centralize` pour cette première validation : ces chemins peuvent démarrer d'autres composants.
- La surcouche démarre par `UltimateHub().run()`, sans `--centralize`, et reprend le verrou de l'ancienne GUI sur le port 8790 ; si une autre GUI occupe déjà ce port, elle ne doit pas créer de doublon.
- Le Hub original possède encore des boutons historiques pouvant démarrer/redémarrer des services, et sa propre fonction de nettoyage des anciens wrappers au démarrage. **L'ouverture de la surcouche n'est donc pas assimilable à un programme strictement « zéro effet » ; l'essai sur le PC doit être accompagné et non effectué à l'aveugle.**
- La nouvelle partie diagnostic n'exécute aucun PowerShell ni processus de réparation. Les sondes de routine ne touchent que les endpoints loopback.
- Le test de conversation peut consommer des ressources du modèle local et ajouter un message à l'historique. Il n'est jamais lancé automatiquement.

## Validation à effectuer avec Vincent

1. Comparer l'empreinte du Hub local avec la version GitHub et **faire une sauvegarde** de toute version locale différente.
2. Vérifier que Core/Room/Ollama sont déjà opérationnels et qu'aucune autre GUI ne possède le verrou 8790, sans tuer les processus existants.
3. Installer uniquement les nouveaux fichiers nécessaires sur une copie de travail cohérente du dépôt ; démarrer manuellement la nouvelle GUI, sans centralisation.
4. Observer les quatre voyants, rafraîchir, simuler une dégradation sans stopper arbitrairement les services ; vérifier qu'aucun doublon n'est apparu.
5. Avec accord explicite de Vincent, cliquer sur « Tester la conversation LOCALE » et confirmer `BAZOR_OK` dans la réponse et le journal.
6. Uniquement après cela, préparer le raccourci Bureau et les boutons de réparation ciblés, avec sauvegarde, confirmation et contrôle après action.

**Ne pas fusionner la PR ni déclarer la V0 opérationnelle sur le PC tant que ces étapes n'ont pas de preuves.**
