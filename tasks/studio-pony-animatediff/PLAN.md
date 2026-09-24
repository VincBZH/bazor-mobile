# BAZOR STUDIO — Plan technique corrigé : Pony V6 XL → AnimateDiff-SDXL
Révision : 2 (24 septembre 2026) · Mission : [issue #161](https://github.com/VincBZH/bazor-mobile/issues/161) · Référence principale : [#149](https://github.com/VincBZH/bazor-mobile/issues/149)

**Statut : PLANIFIÉ ; pas d'installation, de génération ou de test sur le PC prouvé à ce stade.**
**Cible :** Windows 11, RTX 4060 Laptop 8 Go, Studio C:\AI\SimpleStudioV2, ComfyUI déjà installé (chemins et versions à revalider localement).
**Ergonomie :** Vincent ne maîtrise pas les nœuds ni les réglages. Installer, vérifier, générer et réparer via l'interface Studio en un clic ; section Expert optionnelle.

## 1. Architecture impérative de ce nouveau profil
- **Image :** Pony Diffusion V6 XL, checkpoint SDXL. Référence image unique pour le nouveau profil PRO. Confirmer son installation, sa licence et le VAE approprié ; ne pas imposer à l'aveugle un VAE « orangemix » non confirmé comme compatible.
- **Animation :** ComfyUI-AnimateDiff-Evolved avec *motion module SDXL*, priorité à un test comparatif **HotshotXL** (fichier documenté « hsxl_temporal_layers.safetensors ») et **AnimateDiff-SDXL** (fichier officiel « mm_sdxl_v10_beta.ckpt »). L'orthographe proposée « mm_sd_xl_v1_beta2.ckpt » n'est PAS le fichier documenté dans le dépôt officiel : ne pas la coder en dur.
- **Interdiction de compatibilité :** aucun « mm_sd_v15 », « mm_sd_v15_v2 » ou module de mouvement SD1.5 directement avec Pony XL ; aucun SVD/ModelScope à installer pour ce profil.
- **Conserver le fonctionnement existant :** MiniMax H3 et les autres workflows demeurent disponibles hors de ce nouveau profil ; aucun effacement, remplacement global ou seconde installation ComfyUI.
- **Image-to-video réel :** l'image Pony validée doit effectivement conditionner la vidéo par un mécanisme SDXL compatible constaté dans les nœuds installés (par ex. ControlNet/IPAdapter/SparseCtrl approprié). Dupliquer des latents sans conditionnement vérifié ne constitue pas un test I2V réussi.
- **VRAM :** commencer avec 8 images et une petite résolution réellement supportée (dimensions multiples exigées par le workflow), batch=1, puis étendre par fenêtres temporelles si tests OK. L'auteur AnimateDiff évoque ~13 Go pour son exemple SDXL haute résolution ; **8 Go exigent une mesure réelle, sans promesse de compatibilité universelle**.
- **Post-traitement :** RIFE puis RealESRGAN, si réellement installés et compatibles ; FFmpeg/ffprobe pour vérification du MP4. Interpolation et upscale après génération, pas pour cacher une animation incohérente.
- **Profil adulte :** uniquement personnages clairement adultes fictifs ou images autorisées ; conserver les vérifications contre mineurs et sexualisation non consentie de personnes réelles. Ne jamais publier de prompt, image ou log privé dans ce dépôt public.

## 2. Corrections exactes des paramètres
| Ancien concept | Nouveau contrat |
|---|---|
| motion_bucket_id = 128–192 | **SUPPRIMÉ** : paramètre SVD, absent de l'architecture AnimateDiff retenue. |
| strength (nom générique) | Mapper selon le **schéma /object_info local** aux vrais réglages : notamment scale_multival pour l'amplitude du mouvement et effect_multival pour l'influence du motion module ; ne pas inventer une entrée strength universelle. |
| context_offset (proposé) | Ne pas supposer ce champ. Pour Context Options Standard : context_length, context_overlap ; context_stride seulement pour les variantes Uniform qui l'exposent. |
| beta_schedule | HotshotXL : autoselect ou linear (HotshotXL/default) ; AnimateDiff-SDXL : autoselect ou linear (AnimateDiff-SDXL), d'après AnimateDiff Evolved. |
| context_length | HotshotXL : **8 frames** comme premier essai documenté ; régler longueur/chevauchement selon module et VRAM mesurée. |
| motion model | Vérifier famille SDXL, hash, loader et compatibilité avec checkpoint Pony avant toute soumission. |

La présence de la même famille SDXL ne garantit pas, à elle seule, la qualité, la compatibilité complète des LoRA/ControlNet, la conservation du visage ni le fonctionnement sous 8 Go.

## 3. Trois workflows à générer depuis les nœuds effectivement installés
### WF1 : PONY_STILL (image source pour validation)
Nœuds cibles : CheckpointLoaderSimple, CLIPTextEncode (positif/négatif), EmptyLatentImage, KSampler, VAEDecode, SaveImage ; VAELoader uniquement si modèle/VAE validé. Preset initial conservateur : 768×768, batch=1 ; élargir après mesure. Conserver seed, modèle/hash, image, paramètres et statut VALIDÉ / À CORRIGER.

### WF2 : PONY_TO_ANIMATEDIFF_SDXL (courte animation)
Nœuds cibles à confirmer par /object_info : CheckpointLoaderSimple, LoadImage, ImageScale si nécessaire, VAEEncode ou nœud de référence approprié, **Gen2 Load AnimateDiff Model → Apply AnimateDiff Model → Use Evolved Sampling**, Context Options Standard Static/Uniform selon besoin, KSampler, VAEDecode, VHS_VideoCombine. Brancher un conditionnement image SDXL réellement testé. Ne soumettre aucun JSON API qui contient des IDs/classes de nœuds imaginaires.
Validation par paliers : 8 frames → décodage vidéo → 2–3 secondes seulement si conditionnement de la frame initiale et VRAM vérifiés.

### WF3 : POSTPROCESS
Extraction des frames via VideoHelperSuite compatible ou pipeline existant ; RIFE VFI, UpscaleModelLoader → ImageUpscaleWithModel (RealESRGAN compatible), puis sortie MP4 via VHS_VideoCombine/FFmpeg. Contrôler les durées, FPS d'entrée/sortie, dimensions, intégrité de l'encodage, espace disque et temps.

## 4. Nœuds / extensions à inventorier, pas à installer aveuglément
- ComfyUI natif : loaders checkpoint/VAE/image, CLIPTextEncode, KSampler, VAEDecode, SaveImage, UpscaleModelLoader/ImageUpscaleWithModel.
- AnimateDiff Evolved (Kosinkadink), version et nœuds Gen2 ; modèle SDXL dans ComfyUI/models/animatediff_models ou chemin déclaré.
- ComfyUI-VideoHelperSuite : chargeur vidéo / VHS_VideoCombine.
- ComfyUI-Advanced-ControlNet, préprocesseur et/ou IPAdapter_plus **seulement si utiles et compatibles avec le conditionnement SDXL effectivement choisi**.
- RIFE / VFI et RealESRGAN : tester la présence exacte et les versions, sans doublons.
- Confirmer FFmpeg, version CUDA/Torch et VRAM libre ; ne pas créer un second environnement ComfyUI.

## 5. Bouton PRO MODE — parcours débutant en un clic
Le bouton PRO MODE dans Studio sélectionne ce **profil Pony → AnimateDiff-SDXL** sans écraser les autres profils :
1. Vérifier installation/mémoire/espace/nœuds/modèles ; afficher une explication française actionnable si une dépendance manque.
2. Construire et montrer l'image Pony ; boutons VALIDER, CORRIGER et RÉGÉNÉRER.
3. Après validation explicite, compiler **seulement** les paramètres réellement acceptés par le workflow SDXL installé.
4. Libérer proprement les modèles Ollama inutiles, surveiller VRAM, soumettre l'animation, lire la queue et vérifier le fichier réel.
5. Vérifier la première frame, la stabilité du sujet et l'absence d'erreur technique ; si nécessaire demander correction avant post-traitement.
6. Interpoler, upscale, encoder MP4, conserver source + métadonnées + sortie finale.
7. Afficher étapes compréhensibles et STOP/PANIC ; onglet Expert facultatif, ne jamais afficher un faux OK.

## 6. Jalons GitHub, tests bloquants et critères de fin
- [ ] **M0 : inventaire non destructif**. Découvrir chemins réels Studio/ComfyUI ; /object_info ; checkpoints, VAE, motion modules, LoRA, RIFE, RealESRGAN, FFmpeg, taille disque. Sauvegarde/rollback.
- [ ] **M1 : matrice de compatibilité**. Pony V6 réel ; HotshotXL et/ou mm_sdxl_v10_beta ; schémas des nœuds ; première mesure VRAM 8 Go. Décrire toute incompatibilité avant téléchargement.
- [ ] **M2 : WF1 exécution réelle**. API JSON authentique et image sauvegardée/décodable.
- [ ] **M3 : WF2 exécution réelle**. Image validée → 8 frames → 2–3 s après test ; mesurer VRAM, temps, correspondance source/première frame.
- [ ] **M4 : WF3 exécution réelle**. RIFE/upscale si présents, MP4 décodable, FPS cohérents.
- [ ] **M5 : intégration Studio**. Bouton PRO visible, interface claire en français, réglages automatiques avec possibilité Expert, STOP/PANIC et aucun double job.
- [ ] **M6 : reprise durable**. États persistants, sauvegarde avant patch, test de crash/reprise, non-régression MiniMax H3/Studio/Room, aucun téléchargement dupliqué.
- [ ] **M7 : procès-verbal E2E**. Liste exacte des fichiers modifiés, commits, sauvegardes, tests, logs, mesures VRAM/temps/disque et fichier MP4 réellement ouvert sur PC.

**Règle de preuve :** cocher uniquement après trace et test sur la machine ; un JSON écrit ou une réponse HTTP 200 ne prouvent pas qu'une vidéo fonctionnelle a été générée.

## 7. Conservation du travail malgré l'épuisement des crédits Astra
- Source de reprise : issue #161 + présent PLAN.md + tasks/studio-pony-animatediff/checkpoint.json + logs locaux autorisés.
- À **chaque** changement/test vérifié : écrire un checkpoint atomique local (étape, preuves, hash, fichiers modifiés, rollback, prochaine action) puis publier un état technique sans donnée privée sur GitHub.
- À l'ouverture d'une nouvelle session Astra/Work : relire le checkpoint, confronter à l'état réel de ComfyUI et reprendre next_action sans relancer les étapes déjà prouvées.
- Si les crédits sont épuisés : suspendre les analyses gourmandes ; tâches simples via Ollama local si le relais autorisé fonctionne ; aucune promesse de sauvegarde du raisonnement interne, seules les données de travail écrites sont persistantes.
- Aucune commande shell déclenchée depuis des commentaires GitHub ; aucune clé ou données privées dans ce dépôt public. Le travail local et le lancement d'Astra nécessitent une session Work et un relais autorisé distincts.

## 8. Sources des identifiants
- AnimateDiff Evolved README : https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved
- AnimateDiff Evolved Nodes : https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved/blob/main/documentation/nodes/README.md
- AnimateDiff officiel, release SDXL-Beta : https://github.com/guoyww/AnimateDiff#animatediff-sdxl-beta-202311
