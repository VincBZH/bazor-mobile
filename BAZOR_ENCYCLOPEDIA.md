# BAZOR Encyclopédie — état de référence

Version de référence : 2026-09-18

## Règle de fonctionnement

Cette encyclopédie complète `bazor_registry.json`. Le registre est la source de vérité lisible par le mobile. L’encyclopédie explique le contexte, les objectifs, les chemins connus, les règles de validation et les décisions.

Un statut **DONE/OK** n’est valide que si une preuve existe. Pour une tâche de correction de fichier, la preuve attendue est : fichier(s) réellement modifié(s) + tests automatiques réussis + sauvegarde/rapport Action Engine. Une simple analyse ne doit jamais être affichée comme une correction terminée.

Toutes les modifications de BAZOR lui-même passent d’abord par une branche GitHub et la CI avant fusion. Pour les fichiers locaux hors dépôt GitHub, l’Action Engine doit prévalider les changements et conserver une sauvegarde réversible.

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
10. La correction automatique est bornée à 10 tentatives et s’arrête correctement.
11. Le diagnostic vers BAZOR remonte un paquet structuré sans secrets.
12. La durée demandée d’une vidéo est limitée à 10 s maximum. Cela ne signifie pas que le calcul doit durer 10 s.

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
- Durée vidéo utilisateur <= 10 s.
- Image + texte → image/vidéo.
- Concaténation vidéo et reprise depuis la dernière image, à traiter après les P0/P1 de stabilité.

### Qualité
- Analyse post-génération jugée incorrecte ou non concluante.
- Correction automatique souhaitée avec maximum 10 tentatives.
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

## Autres projets BAZOR

Le registre central contient également AI Room, Wii Relay, BAZOR Watch, MODO Viewer, BAZOR Tools, Security et Festival.

MODO Viewer et Festival restent marqués non exécutables par GO tant qu’aucune racine locale sûre n’est reliée à l’Action Engine.

BAZOR Watch est désormais un projet séparé avec ses tâches USB/APK, BLE/watchdog, audio et diagnostic.
