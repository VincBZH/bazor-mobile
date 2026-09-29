# Journal local du Studio BAZOR

`pc-relay/bazor_studio_observer.py` observe **l'installation existante** sur 8191 et ComfyUI sur 8188. Il ne lance pas de génération, ne modifie pas les workflows et ne contacte aucune IA ou service extérieur.

## Raccordement au contrôle de démarrage

Pour un relevé unique, le contrôle de démarrage peut appeler `python pc-relay/bazor_studio_observer.py --once`. Le code de retour est `0` quand un rapport a été écrit, même si Studio ou ComfyUI ne répondent pas : leur état `reachable=false` figure dans le rapport. Une panne de l'observateur retourne `2` et ne doit pas arrêter les autres vérifications.

Pour un journal continu, lancer une seule instance avec `pythonw.exe pc-relay/bazor_studio_observer.py --watch --interval 15` depuis le superviseur BAZOR. `pythonw.exe` évite une nouvelle fenêtre noire ; le superviseur reste responsable d'éviter les doublons et d'indiquer le PID dans son interface compacte. Le script n'installe aucune tâche de démarrage par lui-même.

Les fichiers locaux sont sous `Documents\BAZOR\Studio` par défaut, avec `--output` ou `BAZOR_STUDIO_LOG_DIR` pour un autre dossier. `latest.json` est l'entrée prévue pour le tableau de bord : `studio`, `comfy`, `jobs`, `history`, `console_errors`, `latest_thumbnail`, `log_dir` et `event_log`. `events.jsonl` est borné par rotation ; `observer_state.json` évite de répéter les mêmes événements au redémarrage.

Le prompt est représenté par un court début expurgé et une empreinte SHA-256. Le prompt intégral n'est pas enregistré. Une vignette locale n'est créée que si `--capture-thumbnail` est demandé et si une sortie existe déjà dans le dossier `output` de ComfyUI, avec FFmpeg ou Pillow déjà disponible. Aucun modèle ou logiciel n'est téléchargé. Le journal reste **local et privé** ; il ne faut pas publier les fichiers JSON sur le dépôt GitHub public.

Le script voit les erreurs renvoyées par les API et les fichiers `logs/*.log`, `*.txt`, `*.jsonl` de Studio. Il ne peut pas récupérer rétroactivement une console non redirigée ni une erreur JavaScript visible seulement dans le navigateur. Pour ces deux sources, il faudra raccorder le vrai lanceur et `C:\AI\SimpleStudioV2\app\static\app.js` après examen de leurs versions installées.

## État du correctif vidéo

Les issues #155 et #144 documentent une perte des champs `width`, `height` et `length` lors de la conversion du workflow MiniMax H3 UI vers l'API. L'issue #156 documente un HTTP 400 lors de l'analyse d'un média. Le code actif `C:\AI\SimpleStudioV2\app\workflows.py` et le workflow réel ne sont pas dans ce dépôt. Le journal local permet de rapprocher demande, erreur et sortie ; il ne corrige pas ces deux bugs à lui seul. La qualité vidéo devra être jugée sur un vrai rendu et ses paramètres, pas sur un statut HTTP vert.
