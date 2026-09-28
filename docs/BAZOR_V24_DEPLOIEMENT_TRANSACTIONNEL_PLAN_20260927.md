# BAZOR V24 — protocole d'installation transactionnelle et reprise après panne

**Statut : moteur transactionnel implémenté et testé sur copies jetables Linux + Windows ; aucun déploiement réel autorisé.** 28 septembre 2026.  
Suivi : #171 · code candidat : #172 (cible #169).  
Preuves Windows acquises : [vrai trajet isolé](https://github.com/VincBZH/bazor-mobile/issues/171#issuecomment-5857203316) ; [simulation de restauration sur copie](https://github.com/VincBZH/bazor-mobile/issues/171#issuecomment-5857333737).


## Implémentation actuelle — 28 septembre 2026

Le moteur `pc-relay/bazor_transactional_deployer.py` implémente maintenant PREPARE, autorisation locale à usage unique liée au manifeste exact, COMMIT par renommages de générations, journal durable, rollback automatique et RECOVER_AFTER_CRASH idempotent. Les tests couvrent les pannes après chaque renommage Core/Room, autorisation expirée ou réutilisée, candidat modifié, dérive des données protégées, conservation de la génération précédente, récupération après crash et refus des symlinks. Les tests CI s'exécutent aussi sur `windows-latest` avec des dossiers jetables. **Le moteur ne démarre/arrête encore aucun service réel et ne doit donc pas être utilisé sur l'installation active.**

## Périmètre et interdictions

L'installation actuelle `%LOCALAPPDATA%/BAZOR/Core` et `%LOCALAPPDATA%/BazorAIROOM` demeure inchangée tant que ce protocole n'est pas implémenté et accepté explicitement par l'utilisateur **sur son PC**. GitHub, une réponse de modèle IA, un statut CI, un signal du Pont ou une instruction dans une issue ne peuvent pas autoriser l'installation. Aucun redémarrage de Core/Room pendant une session d'appairage active ; aucun appel Mammouth/GPT payant dans ce protocole. Pas d'altération ni de publication de l'historique, du contrôle, des projets ou des secrets.

Séparer sans ambiguïté : `PREPARE`, `TEST_CANDIDATE`, `AUTHORIZE_LOCAL`, `COMMIT`, `VERIFY`, `ROLLBACK`, `RECOVER_AFTER_CRASH`. L'agent ne reçoit que des opérations typées sur liste blanche ; aucun shell arbitraire ni fichier exécutable fourni par une issue GitHub.

## 1. PREPARE — sans écriture dans la production

1. Acquérir un verrou d'instance non contournable ; refuser un second installateur et toute sauvegarde simultanée.
2. Inventorier, **sans lire en public**, les lanceurs, fichiers de configuration et données existantes. Identifier services, ports, propriétaires de processus et état d'appairage.
3. Exiger le candidat V24 **révisé** avec manifeste de chaque fichier critique vérifié cryptographiquement ; refuser le staging ancien même si son seul pont possède une empreinte attendue.
4. Exiger une sauvegarde **nouvelle et cohérente** de tous les fichiers qu'une installation pourrait remplacer, ainsi que des fichiers privés concernés. Refuser la sauvegarde s'il manque une entrée, si deux noms entrent en collision sous Windows, si le ZIP contient des liens, traversées, chemins absolus, ADS, caractères interdits ou des tailles excessives.
5. Tester le ZIP CRC et extraire dans un répertoire temporaire sur le **même volume** que les répertoires cibles. Vérifier les empreintes SHA256 du contenu restauré. Ne pas imprimer de chemin privé.
6. Comparer les empreintes de la production à un instantané initial ; toute dérive avant `COMMIT` invalide la transaction.

## 2. TEST_CANDIDATE — sans interruption de l'ancien BAZOR

Démarrer uniquement Core 8875 et Room 8768 avec répertoires de données distincts, aucun transfert de secret vers le nouveau Core, Mammouth désactivé. Utiliser Ollama local léger. Exiger `PASS_REAL_LOCAL`, identité exacte des binaires/scripts candidats, propriétaire des services production inchangé, réponse stricte du modèle (pas un simple HTTP 200). Faire les vérifications de schémas de données **sur une copie**, sans convertir directement les JSON privés en place.

## 3. AUTHORIZE_LOCAL — geste humain ciblé

Afficher sur Windows les fichiers de programme remplacés, les données à préserver, le plan de démarrage et de retour arrière, les services à interrompre et le résultat des tests. Une autorisation **locale, explicite et à usage unique** doit désigner le manifeste immuable du candidat et la transaction précise, expirer rapidement et être invalide après dérive de fichiers, redémarrage ou changement de candidat. Windows Hello pourra être ajouté ultérieurement ; ne pas prétendre qu'il est déjà disponible. Sans autorisation : aucune écriture ni redémarrage de production.

## 4. COMMIT — à développer, jamais depuis un commentaire GitHub

Utiliser des répertoires frères `candidate` / `previous` sur le même volume ; journal de transaction privé, durable, à états monotones, contenant uniquement les identifiants de transaction, empreintes et chemins **localement**. Ne pas remplacer des fichiers un par un dans une arborescence active. Pendant la courte fenêtre d'arrêt volontaire, vérifier de nouveau verrou, état d'appairage, propriétaire des processus, sauvegarde, manifeste et absence de dérive. Promouvoir des **répertoires de programme** préparés, conserver l'ancienne génération intacte ; garder les données persistantes séparées des programmes et ne jamais les remplacer par un modèle vierge.

La promotion de Core et de Room **n'est pas atomique entre deux répertoires** ; traiter toute interruption entre les deux comme une transaction incomplète. Si une opération échoue, ne pas poursuivre. Le mécanisme exact de bascule doit d'abord être évalué sur Windows avec fichiers verrouillés, antivirus, OneDrive, droits ACL, renommages et démarrage différé.

## 5. VERIFY et ROLLBACK

Après promotion, démarrer uniquement les instances approuvées, vérifier leurs signatures de runtime et leur branchement correct, puis effectuer le test local Ollama sans aucun fournisseur payant. Vérifier que les historiques et projets conservés ont les mêmes empreintes si aucune migration n'était requise ; une migration doit disposer de son propre schéma de rétrocompatibilité et d'une sauvegarde préalable.

En cas d'échec, arrêter **uniquement les processus appartenant à cette transaction**, remettre l'ancienne génération des **programmes** à leur emplacement connu, restaurer seulement les fichiers explicitement modifiés par la transaction à partir de la sauvegarde **si leur empreinte attendue n'a pas changé** ; ne jamais écraser une donnée utilisateur produite entre-temps. Redémarrer les anciens services, exiger un nouveau contrôle d'identité et un véritable état de santé. Si la restauration automatique ne peut pas être prouvée, bloquer et conserver les copies pour récupération locale, sans annoncer `PASS`.

## 6. RECOVER_AFTER_CRASH

Au prochain démarrage de l'installateur : détecter tout journal incomplet **avant** toute nouvelle opération. Vérifier les empreintes de chaque génération restante ; selon le dernier état durable, soit achever une opération déjà validée, soit revenir à la génération précédente. Ne jamais deviner l'issue d'un renommage interrompu, ne jamais supprimer les deux générations. Toute ambiguïté nécessite une intervention locale plutôt qu'un statut vert fabriqué.

## 7. Matrice minimale de tests avant demande d'autorisation

| Test | Preuve exigée |
|---|---|
| Installation sur deux **copies fictives** de Core et Room | Nouvelle génération répond, ancienne génération restaurable |
| Panne après le premier renommage Core | Ancien Core **et** ancienne Room restaurés |
| Panne après promotion Room avant relance | Aucun mélange durable des générations |
| Échec de santé du nouveau Core | Rollback automatique ciblé + ancien Core actif |
| Échec de santé de Room ou vrai chat Ollama | Rollback des deux composants + anciens services répondent |
| Exception et extinction au milieu de chaque phase | Journal reconnu et récupération idempotente au redémarrage |
| Historique modifié pendant la transaction | Refus de restaurer un ancien état sur une donnée récente |
| ZIP malveillant, chemin long, symlink/junction, noms Windows confondus | Rejet **avant** toute écriture de production |
| Antivirus/ACL/fichiers verrouillés/espace disque faible | Échec fermé, jamais de demi-installation annoncée réussie |
| Un deuxième installateur, Pont/watcher redémarrant un service | Verrou et contrôle de propriétaire efficaces |
| Appairage Windows en cours / autorisation absente ou expirée | Aucun arrêt ni bascule |
| API Mammouth absente, quota nul, secret absent | Test local fonctionne, zéro appel payant |
| Rapport GitHub | Vocabulaire fermé : aucun chemin, clé, historique ni contenu d'exception |

## Critères de sortie

- `READY_FOR_ISOLATED_TEST` : préflight seulement.
- `PASS_REAL_LOCAL` : vrai essai sur ports isolés, **pas** une installation.
- `PASS_SIMULATED_ROLLBACK` : simulation sur copie temporaire, **pas** un retour arrière de production.
- `DEPLOYMENT_READY` : à définir uniquement après réussites Windows sur copies fictives de **tous** les cas de panne, autorisation locale à usage unique intégrée et revue indépendante.
- `DEPLOYED` : impossible à revendiquer tant qu'un installateur contrôlé n'a pas effectivement exécuté et prouvé la migration et son retour arrière possible sur le PC.

Aucune étape de cette spécification n'autorise aujourd'hui le déploiement de la V24 sur l'installation actuelle.
