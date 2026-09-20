# BAZOR Studio — correctif Session S2.2

Correctif pour l’installation existante `C:\AI\SimpleStudioV2`, version 3.0.5.
Date : 20 septembre 2026. Ce livrable stabilise une partie du projet ; ce n’est pas une certification du Studio complet.

## Installation

Télécharger et double-cliquer sur `BAZOR_STUDIO_SESSION_S2_1_CLIC.cmd`.
Le fichier contient son correctif ; aucun téléchargement de modèle ni clé API nécessaire.
Fermer les anciens lanceurs SAFE T2I V1 et DIRECT V4 s’ils attendent une nouvelle exécution.
Le programme vérifie les sources avant de toucher l’installation. S’il ne reconnaît pas une signature, il s’arrête sans remplacer les fichiers.
Il attend qu’aucune génération Studio soit active, identifie l’instance sur 8191, sauvegarde les fichiers modifiés, applique le correctif, réutilise ComfyUI sur 8188 ou le démarre s’il est absent, puis ouvre Studio sur 8191.
Le lancement n’exécute aucun prompt sauvegardé et aucune génération automatique.

## Complément S2.2 — arrêt Windows refusé

Le journal utilisateur du 20 septembre confirme : préflight passé, mais accès refusé à Stop-Process pour le Studio PID 21592. Aucun fichier applicatif n’avait été modifié. Ce retour ne prouve pas un problème de workflow ni de modèle.

En cas de PermissionDenied, l’installateur lance désormais un petit assistant d’arrêt via la demande UAC standard de Windows. Après accord, cet assistant revérifie application, dossier, PID, port et absence de tâche active, puis arrête uniquement ce Studio. Il n’installe rien et ne démarre aucun serveur. Le processus principal poursuit avec ses droits habituels pour éviter de recréer un Studio administrateur. Un refus UAC annule avant installation. ComfyUI reste en marche.

Treize scénarios PowerShell isolés sont fournis pour les refus réseau, PID, dossier, application, processus, port, tâches actives, accès et le chemin réussi. Ils simulent les interactions système : aucune UAC réelle ni génération GPU n’est validée par ces scénarios. Les dix scénarios d’arrêt ont été exécutés avec succès sous Windows PowerShell 5.1 en CI ; trois cas supplémentaires couvrent la reconnaissance des refus directs ou encapsulés. Voir la PR GitHub pour le résultat du paquet final. Ne pas déclarer l’incident résolu sur le PC avant le retour runtime. Journal spécifique : `logs\session-s2-elevated-stop.log`.

Le convertisseur UI/API antérieur est conservé comme repli, notamment le hotfix H3 déjà présent dans le dépôt BAZOR. Un test couvre cette conservation et un autre injecte une panne en cours d’écriture pour vérifier la restauration de tous les fichiers déjà modifiés.

## Changements

- Nouvelle création vierge au démarrage : aucun ancien prompt, style, avatar ou résultat repris automatiquement.
- Historique conservé dans la galerie. Les anciennes tâches terminées ne remplissent plus l’activité de la session actuelle.
- Bouton Nouvelle création et trois exemples Découverte, sans génération déclenchée par le choix d’un exemple.
- Sources retirées en T2I et T2V côté navigateur et serveur. I2I/I2V/V2V exigent une référence choisie.
- Les workflows H3 texte contenant encore un chargeur image/vidéo sont refusés avant soumission.
- Lecture complète des octets reçus avant analyse, validation et conversion des images en JPEG RGB ; sélection d’un modèle Ollama confirmant la capacité vision.
- Analyse, correction et retour asynchrone attachés à un job précis. Aucune analyse automatique d’une ancienne création.
- Corrections bornées à 10 maximum, intention initiale conservée, arrêt possible, exclusion des générations simultanées pendant l’analyse locale.
- Affichage graphique des nœuds et connexions du workflow API réellement enregistré ; export du même graphe. Il s’agit d’un visualiseur, pas d’un éditeur ComfyUI complet.
- Messages de refus du moteur lisibles avec nœud et entrée concernés ; détails conservés au diagnostic.
- Choix initial préférentiel d’un checkpoint généraliste reconnu par son nom. Un modèle inconnu n’est pas choisi automatiquement. Cette préférence n’est pas une garantie de sûreté du contenu.

## Complément S2.1 — dimensions H3

Le message « réglage largeur/hauteur introuvable » provenait d’une recherche limitée aux champs déjà présents ensemble dans le JSON. Le correctif examine aussi le schéma `/object_info` du moteur installé : il renseigne les entrées de dimensions déclarées de type INT, même si l’export les omet. Les paires width/height, video_width/video_height et image_width/image_height sont reconnues. Les réponses de conversion imbriquées sont déballées.

Les dimensions sont modifiées à l’entrée du nœud de génération sans changer les constantes partagées en amont. Les nœuds natifs H3 reconnus sont synchronisés ; leur longueur suit la grille native 17k+5 (49 images demandées deviennent 56, soit environ 2,33 secondes à 24 fps). Le résumé d’interface reste une durée indicative demandée, le graphe exporté contient la valeur réellement envoyée.

Si aucun contrôle n’est identifiable, le programme refuse la soumission et nomme les nœuds et leurs entrées. Le JSON exact du workflow qui a produit le dernier message n’a pas été fourni : les huit cas de test supplémentaires vérifient ces corrections, pas la compatibilité de toutes les extensions H3. La mention non validée « Adapté à 8 Go » est retirée.

Le fichier CMD remplace le précédent S2 et prend en charge une installation S2 déjà appliquée. La version technique vérifiée au démarrage devient `3.0.5-session-s2.1` (désormais `3.0.5-session-s2.2` avec la révision suivante).

## Refus H3 du journal fourni

| Élément | Référence absente du workflow | Variante présente dans le journal |
|---|---|---|
| UNET | minimax_h3_fl2va_pruned_int8_convrot.safetensors | minimax_h3_fl2va_pruned_w4a8_mixed.safetensors |
| VAE vidéo | minimax_h3_video_vae_fp16.safetensors | minimax_h3_video_vae_int8_convrot.safetensors |
| Encodeur | qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | qwen3vl_4b_int8_convrot.safetensors |

Le correctif vérifie ces noms dans l’inventaire **vivant** de ComfyUI. Il ne change pas de famille H3 vers Wan et ne remplace pas une vidéo VAE par un audio VAE.
Pour Qwen 4B, il exige le type `krea2`, le nœud `ClipProjApply` et la projection déjà installée `mmh3-4b-ClipProj-v3-mlp.safetensors`, puis relie le conditionnement à cet adaptateur. Si une pièce manque, le message la nomme et le graphe n’est pas envoyé.
L’encodage CLIP passe sur CPU quand le chargeur le propose : moins de concurrence VRAM, mais potentiellement plus lent.
Les fichiers des modèles et les modèles eux-mêmes ne sont pas modifiés.
La compatibilité de quantification, la version du nœud ClipProj et la mémoire réellement disponible restent à vérifier lors de l’exécution GPU. L’auteur de ClipProj indique que les matrices v3 exigent le nœud 0.1.13 ou ultérieur. Aucune extension n’est mise à jour silencieusement par ce correctif.

## Vérifications effectuées

- 30 tests Python ciblés : références, modèles, adaptation 4B, médias en morceaux, vision, correspondance job/prompt, refus si GPU occupé, installation idempotente, sauvegarde et restauration.
- 33 tests existants de workflow et API, sur moteur de test. La fixture expose maintenant `/api/show` et deux tests utilisent I2V pour vérifier une entrée image (une référence en T2V est désormais interdite).
- 13 scénarios JavaScript unitaires : démarrage vierge, sélection explicite, désactivation de l’analyse sans rendu sélectionné, source selon le mode, reset et réponse d’analyse périmée.
- Syntaxes Python et JavaScript vérifiées.
- Aucun test de rendu IA réel. Aucun test d’exécution Windows du lanceur PowerShell dans cet environnement Linux.
- Test navigateur complet préparé, mais non exécuté : Chromium indisponible, téléchargement bloqué. Le rendu visuel de l’interface n’est donc pas certifié ici.

## Ce qui reste pour terminer l’ensemble du projet

1. Installer le correctif sur le PC, vérifier les versions ComfyUI/ClipProj et réaliser une génération neutre image puis vidéo avec les modèles réellement chargés.
2. Mode enfant : non livré. L’isolation de galerie, le verrouillage du profil et le filtrage fiable des entrées ET des sorties doivent être implémentés et testés avant de présenter l’application comme adaptée aux enfants. Une liste de mots interdits ou un négatif ne suffit pas.
3. Routeur maître complet avec inpainting, outpainting, ControlNet, IPAdapter, upscale, interpolation et API Seedance : non livré par ce correctif.
4. V2V demeure la fonction existante de réanimation de la première image ; ce n’est pas une conservation du mouvement de toute la vidéo.
5. Aucun générateur de contenu sexuel explicite ajouté. Les protections existantes du moteur de prompts sont conservées.

## Sauvegarde et preuve locale

`backups\SESSION_S2_<date>\` contient les originaux et le manifeste avant/après.
`logs\session-s2-install.json` journalise quoi, pourquoi, par qui, quand et les SHA-256.
`logs\session-s2-runtime.json` est écrit uniquement après réponse HTTP de la bonne instance : il distingue `http_verified` et `generation_gpu_verified` (ce dernier reste faux).
Dans le ZIP : `rollback.py --root C:\AI\SimpleStudioV2` restaure les fichiers de la dernière transaction si rien ne les a modifiés depuis. Arrêter Studio avant la restauration.
Les modèles, les bases de données, les créations, les fichiers Room et les clés restent dans leur emplacement existant.

## Sources techniques consultées

- Sources Studio : archive utilisateur AI_Simple_Studio_BAZOR_V3_3.0.5_PLAYWRIGHT_INSTALL_FIX_20260917.zip, puis comparaison avec les scripts de réparation de bazor-mobile.
- [Nœuds H3 natifs de ComfyUI](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_h3.py) : dimensions et grille temporelle 17k+5.
- [Ollama : images dans l’API](https://docs.ollama.com/capabilities/vision) : transmission des images en base64 au modèle vision.
- [ClipProj, source du nœud](https://github.com/nicolab28/ComfyUI-ClipProj/blob/c01ba8fb8f41b4f2094dbd0b185cdc238fb6134c/clipproj_nodes.py) : contrat du nœud de projection.
- [ClipProj : compatibilité et versions](https://github.com/nicolab28/ComfyUI-ClipProj) : adaptation Qwen 4B et exigence de version pour les matrices v3.
- [MiniMax H3 W4A8 expérimental](https://huggingface.co/Kijai/MiniMax-H3-experimental) : contraintes du format et du VAE.

Ces sources soutiennent les contrats d’interface, pas une promesse de performances sur le PC cible.
