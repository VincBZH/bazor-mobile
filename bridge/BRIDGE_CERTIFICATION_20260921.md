# Certification BAZOR ↔ Mammouth ↔ Ollama — 2026-09-21

STATUS: BAZOR_BRIDGE_E2E_BLOCKED

## État réellement vérifié
- Dépôt : VincBZH/bazor-mobile.
- PR #150 : ouverte, brouillon, non fusionnée.
- Issue #151 : ouverte, existante.
- Branche : fix/mammouth-ollama-bridge-runtime.
- Révision de départ : f553829e8ca207e7846c62ba0f88660cf7e29ea4.
- Sources récupérées par l’API GitHub à cette révision dans une copie isolée.
- Aucun dépôt ni fichier du PC Windows de Vincent n’a été modifié.
- Aucun modèle réel utilisé, aucun appel externe Mammouth, aucun téléchargement de modèle.

## Corrections réalisées
- Footer curl : vrai retour à la ligne, CRLF ou antislash-n littéral ; statut terminal strict ; JSON conservé.
- Test initial : 3 PASS / 1 FAIL (antislash-n littéral), défaut reproduit avant correction.
- Clé Mammouth fournie à curl via stdin/config, absente de ses arguments ; redirection HTTP désactivée.
- Limites entrées, sorties, tokens et temps ; arrêt sur 401/403 ; trois essais maximum, uniquement transitoires et sur le même modèle.
- Test du pont : un seul appel Mammouth, 64 tokens de sortie maximum par étape.
- Modèle réel distinct du modèle demandé ; absence de modèle ou alias de routage non résolu = échec.
- Trois enveloppes corrélées, provenance explicite, absence de repli Ollama si Mammouth échoue.
- Marqueur exact requis pour le mode de certification ; une sous-chaîne ne suffit plus.
- Les réponses sont des données ; aucune transmission à ActionEngine.
- Journal JSONL sans contenu généré : métadonnées et empreinte SHA-256 du contenu.
- Core importable sans démarrer ses serveurs ; signatures du Core et du watcher synchronisées.
- Endpoint Core /api/v1/chat conserve le résultat bridge et fournit aussi answer/request_id.
- Santé du Core : PID, chemin du code, chemin du journal et capacité mammouth_ollama.
- Test réel exige une URL Room locale explicite et vérifie l’identité/signature du Core avant toute dépense.

## Vérifications exécutées
- 24 tests de contrat/transport/Core/Watcher/FileBus/routeur Room : PASS.
- 6 tests du protocole Studio : PASS.
- 1 régression de sélection du contexte Studio : PASS.
- Compilation des six fichiers Python modifiés/ajoutés : PASS.
- Les quatre tests Mammouth préexistants sont aussi exécutés par le groupe de régression.
- Le test HTTP utilise le vrai ApiHandler sur un port éphémère avec fournisseurs simulés.
- Le test curl utilise le vrai exécutable sur un serveur de test loopback avec une fausse clé.
- Ces deux tests ne sont PAS des preuves de disponibilité des fournisseurs réels.

## Blocages et limites non résolus
- Environnement d’exécution disponible : Linux, distinct du PC Windows de Vincent.
- MAMMOUTH_API_KEY absente de cet environnement seulement ; présence sur Windows non vérifiable.
- Sur ce Linux : ports 11434, 8775, 8776, 8765 inaccessibles (Errno 111).
- Tentative par http://127.0.0.1:8776 : URLError: <urlopen error [Errno 111] Connection refused>.
- Aucun statut HTTP Mammouth : appel non effectué.
- Diagnostic prédéfini, lecture seule, envoyé via issue #152 ; aucune réponse lors des vérifications.
- Le watcher étudié synchronise origin/main. Il ne propose pas de déploiement de branche de PR ni de certification du pont dans sa liste de commandes.
- Fusionner pour déclencher l’installation contournerait la condition PASS réel avant fusion : aucune fusion effectuée.
- PID, version active, modifications non commises, logs, modèles et écoute réseau du PC Windows restent inconnus.
- L’interface Room réellement active ne peut pas être identifiée. L’aller-retour visible dans Room reste NON TESTÉ. Le test de routage Room hors ligne ne le prouve pas.
- Le budget monétaire préexistant reste une estimation dépendante des prix connus ; aucun plafond financier exact n’est certifié pour un alias à tarification inconnue. La limite de tokens est imposée.
- Windows/curl, redémarrage de l’instance unique, installation et régressions réelles après installation restent NON TESTÉS.
- Le registre/encyclopédie n’ont pas été marqués PASS.

## Preuves
Dans bridge/evidence/bridge-certification-20260921/ :
- offline-bridge.log
- routing.log
- studio-protocol.log
- runtime-attempt-linux.json
- summary.json

Le journal réel, après exécution sur le PC, serait celui indiqué par health.journal_path (pc-relay/BAZOR_DATA/journal.jsonl dans ce code). Son existence sur Windows n’est pas affirmée.

## Rollback
L’état initial des fichiers existants est conservé dans le commit f553829e8ca207e7846c62ba0f88660cf7e29ea4.
Le commentaire de PR accompagnant ce commit donne la commande git revert avec son SHA exact.
Aucun rollback du PC nécessaire : aucune installation ni modification effectuée sur Windows.
Exécuter un éventuel revert uniquement dans une copie propre, après préservation des changements non commis. Aucun reset --hard.

## Validation restante
Sur le PC réel, identifier et sauvegarder le code actif et ses changements, déployer la branche de façon réversible, recharger seulement le Core identifié, vérifier écoute loopback Ollama et modèles installés, puis utiliser :
python pc-relay/test_mammouth_ollama_runtime.py --room-url http://127.0.0.1:PORT_REEL_DU_GATEWAY
Le port doit provenir de l’inventaire réel ; 8776 n’est pas supposé actif. La commande n’est pas un installateur et ne démarre aucun service.

