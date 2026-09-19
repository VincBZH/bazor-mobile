# BAZOR Encyclopédie — état de référence

Version de référence : 2026-09-19

## Règle de fonctionnement

Cette encyclopédie complète `bazor_registry.json`. Le registre est la source de vérité lisible par le mobile. L’encyclopédie explique le contexte, les objectifs, les chemins connus, les règles de validation et les décisions.

Un statut **DONE/OK** n’est valide que si une preuve existe. Pour une tâche de correction de fichier, la preuve attendue est : fichier(s) réellement modifié(s) + tests automatiques réussis + sauvegarde/rapport Action Engine. Une simple analyse ne doit jamais être affichée comme une correction terminée.

Toutes les modifications de BAZOR lui-même passent d’abord par une branche GitHub et la CI avant fusion. Pour les fichiers locaux hors dépôt GitHub, l’Action Engine doit prévalider les changements et conserver une sauvegarde réversible.

### Règle obligatoire — synchronisation à chaque version

Dès qu'une **version, build, patch, APK, installateur, ZIP livrable ou release** BAZOR est généré, l'Encyclopédie et le registre doivent être synchronisés **dans le même cycle de livraison**. Une version n'est pas considérée complètement livrée si sa version, ses changements, ses tests, ses chemins et ses limites réelles ne sont pas inscrits ici et/ou dans `bazor_registry.json`.

Le mécanisme standard est `pc-relay/bazor_encyclopedia_sync.py`. Les générateurs/lanceurs BAZOR doivent l'appeler avec le composant et la version produite. La synchronisation doit être idempotente, journalisée et ne jamais supprimer l'historique des versions.

## Priorité actuelle : AI Simple Studio

Objectif immédiat : obtenir une version réellement utilisable avant d’ajouter de nouvelles fonctions.

Chemin local principal : `C:\AI\SimpleStudioV2`.

ComfyUI portable connu : `C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI`.

Ports de référence :
- ComfyUI : 8188
- AI Simple Studio : 8191

Matériel cible : RTX 4060 8 Go. Les réglages doivent privilégier la stabilité VRAM.

### Ressources H3 déjà signalées présentes

- `minimax_h3_fl2va_pruned_w4a8_mixed.safetensors`
- `qwen3vl_4b_int8_convrot.safetensors`
- `mmh3-4b-ClipProj-v3-mlp.safetensors`
- workflow `MiniMax_H3_FL2V_8GB_VRAM.json`

Une ancienne référence `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` a déjà provoqué une erreur ComfyUI `clip_name ... not in list`. Elle ne doit pas rester dans un chemin actif sauf si le fichier existe réellement et est accepté par le nœud concerné.

## Définition de « Studio opérationnel »

Le Studio n’est déclaré opérationnel que lorsque les points suivants sont vrais en même temps :

1. Le lancement ne ferme pas silencieusement les fenêtres en cas d’échec.
2. Une instance ComfyUI saine déjà ouverte sur 8188 est réutilisée, pas dupliquée.
3. Le Studio tourne sur 8191 sans collision.
4. Le workflow MiniMax H3 8 Go se charge avec uniquement des ressources réellement installées.
5. Le payload envoyé à ComfyUI est validé avant soumission.
6. Une génération de test atteint ComfyUI et revient avec un résultat exploitable.
7. Les erreurs ComfyUI/fetch/404 sont affichées avec leur vraie cause.
8. La galerie distingue masquer, supprimer et récupérer.
9. L’analyse post-génération produit un résultat traçable.
10. La correction automatique s’arrête sur succès, stagnation, erreur technique répétée, annulation utilisateur ou contrainte réelle ; BAZOR n’impose pas de plafond artificiel fixe.
11. Le diagnostic vers BAZOR remonte un paquet structuré sans secrets.
12. La durée n’est pas bridée artificiellement : sur RTX 4060 8 Go, les segments courts (~6 s) sont privilégiés pour la stabilité et les durées longues sont construites séquentiellement (ex. film ~30 s = 5 × ~6 s).

## Bugs et demandes déjà rapportés

### Démarrage / installation
- Fenêtres rouges ou CMD qui se ferment avant lecture du diagnostic.
- Messages « ComfyUI déjà ouvert » mal gérés.
- Besoin d’empêcher les doubles instances.
- Ancien lancement Playwright depuis un chemin d’extraction temporaire ZIP devenu inexistant.
- Besoin d’un démarrage idempotent.

### H3 / modèles / workflows
- Erreur d’encodeur introuvable.
- Erreur confirmée de type `clip_name ... not in list`.
- Besoin d’un workflow H3 adapté à 8 Go VRAM.
- Besoin de presets qui correspondent réellement aux modèles installés.
- Fluidité jugée faible sur certaines générations.

### Interface et génération
- Presets souhaités : Réaliste, Photo, Noir & Blanc, Corps entier.
- Réglages optimisés automatiques.
- Durée vidéo sans plafond produit arbitraire ; segmentation automatique selon les contraintes réelles du workflow/GPU.
- Image + texte → image/vidéo.
- Concaténation vidéo et reprise depuis la dernière image, à traiter après les P0/P1 de stabilité.

### Qualité
- Analyse post-génération jugée incorrecte ou non concluante.
- Correction automatique sans plafond artificiel fixe ; arrêt intelligent sur succès, stagnation, répétition de la même erreur, contrainte réelle ou annulation.
- Aucun score ne doit être affiché comme valide s’il n’est pas rattaché à une génération analysée.

### Galerie
- Masquage, suppression et récupération doivent être distincts et sûrs.
- Ne jamais perdre un fichier parce qu’un simple masquage a été interprété comme suppression.

### Diagnostic
- Bouton « Diag to GPT/BAZOR » attendu.
- Une erreur doit remonter automatiquement avec étape, erreur exacte, contexte et logs utiles.
- Les clés et secrets sont exclus des diagnostics.

## Tableau de tâches

La liste exécutable et dynamique se trouve dans `bazor_registry.json` sous le projet `simple-studio.tasks`.

Ordre de traitement :
- P0 : bloquants avant toute déclaration « utilisable ».
- P1 : fonctions indispensables à l’usage quotidien.
- P2 : optimisation après stabilisation.

Les dépendances indiquées dans le registre doivent être respectées. Une tâche ne doit pas être marquée terminée uniquement parce qu’une IA a répondu. Elle doit produire la preuve exigée par son champ `proof_required`.

## Répartition IA

BAZOR doit utiliser plusieurs avis au lieu d’un seul moteur :

- Mammouth/Qwen : lecture de code et correctifs minimaux.
- Mammouth/Gemini : analyse de cohérence, tests, dépendances et workflow.
- Mammouth/Claude : architecture, risques, séquencement et revue indépendante.
- Mammouth/Mistral : contrôles rapides, texte, cohérence de configuration légère.
- Ollama local : collecte locale, première passe, tâches répétitives et économie de crédits.

Mammouth ne doit pas appliquer directement une modification critique par défaut. Il sert d’abord de seconde lecture. L’Action Engine applique seulement une action structurée autorisée et vérifiable.

## Pipeline de validation

1. Lire l’état réel et les fichiers autorisés.
2. Demander une proposition à l’IA principale.
3. Pour les P0 et les changements structurants, demander au moins un second avis Mammouth.
4. Préparer les modifications dans un bac à sable.
5. Exécuter les tests syntaxiques/déterministes dans le bac à sable.
6. Si les tests échouent : ne rien écrire sur la cible.
7. Si les tests passent : sauvegarder l’original, appliquer, puis retester la cible.
8. Conserver la preuve : fichiers, hash avant/après, tests, rapport.
9. Mettre à jour l’état dynamique de la tâche.
10. Ne passer à la dépendance suivante que lorsque les critères de DONE sont remplis.


## État de l’orchestration mobile

Le Command Center mobile lit dynamiquement les tâches définies dans `bazor_registry.json`. Pour les projets qui possèdent un tableau `tasks` :

- le bouton **SUIVANTE** affiche la prochaine tâche exacte, pas une consigne générique de sous-projet ;
- les dépendances empêchent une tâche aval de démarrer trop tôt ;
- le statut de chaque tâche est synchronisé dans l’état central BAZOR ;
- **DONE** exige une modification réelle avec tests réussis ;
- **VÉRIFIÉ** est réservé au cas où le moteur démontre que les critères sont déjà satisfaits sans modification ;
- **ANALYSE SEULE** n’est jamais assimilé à un succès ;
- **BLOQUÉ** conserve la cause et arrête l’AUTO ;
- la preuve affiche fichiers, tests, moteur et modèle réellement utilisés.

Pour les tâches Studio P0, BAZOR demande avant l’exécution jusqu’à deux secondes lectures Mammouth selon `preferred_models`. Les avis sont consultatifs : ils sont transmis au moteur d’exécution, mais ne peuvent pas écrire directement dans les fichiers. Le modèle réellement retourné par Mammouth est mémorisé, afin de détecter un éventuel routage différent du profil demandé.

## Sécurité d’exécution / bac à sable

Toute modification produite par l’Action Engine passe désormais par un **préflight obligatoire** avant la cible réelle :

1. les versions actuelles des fichiers concernés sont copiées dans `BAZOR_DATA/ACTION_SANDBOX/<request_id>` ;
2. un dépôt Git local temporaire est initialisé quand Git est disponible ;
3. l’état de référence est enregistré ;
4. les versions candidates sont écrites uniquement dans ce bac à sable ;
5. `git diff --cached --check` et les tests déterministes adaptés au type de fichier sont lancés ;
6. si un test échoue, la cible réelle n’est jamais touchée ;
7. si le préflight passe, l’original est sauvegardé dans `ACTION_BACKUPS`, la modification réelle est appliquée puis retestée ;
8. un rapport est conservé dans `ACTION_REPORTS`.

Pour le code BAZOR lui-même, s’ajoute une seconde barrière : branche GitHub isolée + CI verte avant fusion vers `main`.

## Qualité des secondes lectures Mammouth

Les premières revues de test #31/#32/#33 ont produit des réponses trop générales et ont indiqué `mistral:latest` comme modèle effectif malgré des profils distincts demandés. Elles ne sont **pas** considérées comme des validations techniques du Studio et ne doivent pas faire avancer une tâche.

Conséquence : le tableau dynamique conserve le profil demandé **et** le moteur/modèle réellement retourné. Une seconde lecture vague ne vaut jamais preuve. Le travail Studio reste jugé uniquement sur les fichiers réellement lus et les critères DONE du registre.


## Exécution autonome sûre

Le watcher GitHub accepte désormais une file `[bazor-task:ID]` limitée aux IDs déjà présents dans le registre. Le texte libre d’une issue ne devient pas une commande d’écriture. Pour une tâche prédéfinie :

1. le watcher retrouve uniquement la définition du registre ;
2. il refuse la tâche si ses dépendances ne sont pas terminées ;
3. il demande les secondes lectures Mammouth prévues par `preferred_models` ;
4. il lance ensuite l’exécution finale en mode AUTO avec l’action et les critères DONE du registre ;
5. l’Action Engine effectue le préflight Git sandbox avant toute écriture ;
6. si aucune modification n’est prouvée, une seule relance corrective est autorisée ;
7. le statut final est limité à DONE, VERIFIE, ANALYSE_SEULE ou BLOCKED ;
8. le résultat, les avis IA, le moteur réel, les fichiers, les tests et la preuve de préflight sont recopiés dans l’état mobile central.

Cette file ne transmet aucune commande shell depuis GitHub et ne permet pas d’inventer une tâche hors registre.

## Sélection du contexte local

Le contexte donné aux IA n’est plus choisi uniquement selon la date de modification des fichiers. Le moteur donne maintenant un score supérieur aux chemins correspondant aux mots de la tâche exacte. Une tâche H3 privilégie donc les workflows/fichiers H3 ; une tâche launcher/démarrage privilégie les lanceurs correspondants. Les dossiers runtime, logs, sauvegardes et sandboxes sont exclus du scan.

## Incident réel Studio — 2026-09-19

Une génération réelle depuis l'interface a démontré que la qualification précédente 47/47 couvrait **configuration, services, syntaxe et connectivité**, mais pas encore une génération vidéo complète de bout en bout. La certification ne doit plus employer le mot 100% opérationnel tant qu'un smoke test E2E réel n'a pas produit un média.

Erreurs ComfyUI observées sur la chaîne MiniMax H3 active :

- CLIP rejeté : `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`; options réellement offertes : `qwen3vl_4b_int8_convrot.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`.
- VAE rejeté : `minimax_h3_video_vae_fp16.safetensors`; option H3 vidéo réellement offerte : `minimax_h3_video_vae_int8_convrot.safetensors`.
- UNET rejeté : `minimax_h3_fl2va_pruned_int8_convrot.safetensors`; option H3 réellement offerte : `minimax_h3_fl2va_pruned_w4a8_mixed.safetensors`.
- Le Studio affiche aussi : `Workflow MiniMax H3 incompatible : réglage largeur/hauteur introuvable`. Le mapping UI → workflow doit être dérivé des vrais nœuds/champs du workflow actif, sans node_id inventé.
- L'analyse du rendu échoue avec `Failed to load image or audio file`. Le chemin vision doit transmettre un média réellement accessible au moteur local (fichier/base64/blob selon l'API), et non une URL locale que le moteur ne sait pas charger.

Tâches ajoutées au registre :
- `STUDIO-P0-008` : aligner les loaders CLIP/VAE/UNET.
- `STUDIO-P0-009` : réparer le mapping largeur/hauteur.
- `STUDIO-P0-010` : réparer le chargement média pour l'analyse vision.
- `STUDIO-P0-011` : imposer une génération E2E sûre avant certification complète.

Règle de certification mise à jour : les contrôles statiques/runtime peuvent être verts sans que la génération soit réellement utilisable. Une preuve E2E réelle est obligatoire avant d'afficher **pleinement opérationnel / 100%**.

## Autres projets BAZOR

Le registre central contient également AI Room, Wii Relay, BAZOR Watch, MODO Viewer, BAZOR Tools, Security et Festival.

MODO Viewer et Festival restent marqués non exécutables par GO tant qu’aucune racine locale sûre n’est reliée à l’Action Engine.

BAZOR Watch est désormais un projet séparé avec ses tâches USB/APK, BLE/watchdog, audio et diagnostic.


## Coordination BAZOR Trio — GPT + Ollama + Mammouth

Depuis le 19/09/2026, le mode de travail prioritaire pour Studio est :

- **GPT** : coordinateur et arbitre final ;
- **Ollama local** : audit du code réel présent sur le PC, sans dépendre d'un upload externe ;
- **Mammouth** : seconde revue indépendante en ligne ;
- **BAZOR** : orchestration, collecte du contexte local, journalisation et handoff.

Le marqueur `[TO_BAZOR_TRIO]` demande une revue croisée. Un retour Trio n'est accepté comme livraison que s'il contient des fichiers réellement lus, l'avis Ollama, l'avis Mammouth, un patch candidat et un plan/résultat de tests. Un simple `STATUS: OK` vide vaut **NON LIVRÉ**.

Le relay a été corrigé le 19/09/2026 pour envoyer les gros handoffs GitHub via **stdin JSON** au lieu de la ligne de commande Windows, afin d'éviter les blocages dus à la limite de taille de `CreateProcess`.



## BAZOR AI Room — état et cible

Référence connue : **ROOM v1.8.4**. Elle possède déjà historique JSONL, mémoire/brain, pièces jointes texte/code, workspaces, permissions, PANIC, diagnostic automatique, LOG GPT et clients GPT/Ollama/Mammouth.

Cible de la prochaine mise à jour consolidée : **ROOM v1.9** avec :
- import natif de conversation `.md/.jsonl` avec `conversation_id`, tags, auteurs et déduplication ;
- vue d'état commune BAZOR Core / GPT / Ollama / Mammouth / bridges ;
- accès direct Bibliothèque/Encyclopédie avec alerte de fraîcheur ;
- handoff multi-IA normalisé ;
- version/rollback/self-test avant remplacement ;
- conservation intégrale de `data/` et de la mémoire.



## Test réel Studio V3 — 19/09/2026 vers 14:38

Un nouveau test utilisateur confirme :
- ComfyUI connecté et `/api/health` retourne `ready=true` ;
- checkpoints image visibles : `NoobAI-XL-v1.1.safetensors`, `sd_xl_base_1.0.safetensors` ;
- `/object_info` répond correctement ;
- Autopilot Chrome/CDP sait se rattacher et ouvrir le menu profil ;
- **mais** le workflow H3 reste bloqué sur `réglage largeur/hauteur introuvable` ;
- l'analyse post-génération affiche toujours `Failed to load image or audio file` ;
- plusieurs jobs récents sont `error / Demande refusée` ou `lost`.

Conclusion : la connectivité de base est saine, mais la chaîne de génération/QA Studio n'est pas encore certifiable. Les P0 Trio restent prioritaires.



<!-- BAZOR_VERSION:BAZOR Studio V4 Trio Chain::2026.09.19.3 -->
### BAZOR Studio V4 Trio Chain — 2026.09.19.3
- Généré : 2026-09-19
- Statut : PATCH
- Changements : chaîne autonome Studio P0 = Ollama local → revues Mammouth Claude/Gemini → arbitrage GPT-5.6 Sol → au besoin une réparation locale → nouvelle revue.
- Sécurité : aucune revue externe n'écrit directement ; Action Engine, sandbox, tests et rollback restent obligatoires.
- Limite : indisponibilité d'un reviewer externe ne bloque pas un résultat local déterministe suffisamment prouvé.
## BAZOR AI ROOM V2.4 — pipeline autonome (2026-09-19)

Référence registre : `ai-room` dans `bazor_registry.json` version `2026.09.19.4`.

Chaîne P0 enregistrée :
- `AIROOM-P0-001` : déployer la V2.4 dans `%LOCALAPPDATA%\BazorAIROOM` via BAZOR Action Engine, avec preflight, backup, tests et rapport.
- `AIROOM-P0-002` : prouver le runtime local sur `127.0.0.1:8765` et tester l'interface/API.
- `AIROOM-P0-003` : prouver le routage réel Ollama / Mammouth et les fallbacks, sans faux statut disponible.
- `AIROOM-P0-004` : qualification finale ; `DELIVERED` interdit tant que tous les gates et preuves ne sont pas PASS.

Machine d'état obligatoire :
`PROTOCOL_READY -> CODE_PATCHED -> CI_PASS -> RUNTIME_PASS -> DELIVERED`.

Règle de récupération :
fichier/message incomplet, handoff absent, crash, timeout, réponse provider vide ou état incohérent => `DEFAULT_RECOVERY`, incident horodaté, pas de `DONE`, retry transitoire unique, puis changement de provider ou mise en file d'attente.

GitHub reste un bus de coordination et de preuve ; aucun shell/exec/eval arbitraire reçu depuis GitHub n'est autorisé.


<!-- BAZOR_VERSION:BAZOR AI ROOM TRIO::2026.09.19.1 -->
## BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth

- Nom officiel: **BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth**.
- Un seul canal utilisateur; aucune copie manuelle entre IA.
- Identités strictes: GPT=coordinateur/arbitre, Ollama=local/technique, Mammouth=seconde lecture externe, BAZOR Core=orchestration/sécurité.
- Bootstrap contexte obligatoire au début de chaque nouvelle conversation/journée: identités, état courant, Encyclopédie, Registry, résumé projet, handoffs FileBus, capacités réelles.
- Mémoire locale structurée par projet/conversation avec résumé, décisions, faits sourcés, tâches ouvertes et index.
- À chaque build: Encyclopédie + Registry doivent être mis à jour ensemble avec version, changements, tests, preuves runtime et rollback.
- Spécification: `bridge/AI_ROOM_TRIO_PROTOCOL.md`.
