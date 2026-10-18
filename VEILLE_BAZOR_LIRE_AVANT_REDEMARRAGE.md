# BAZOR Veille — installation sur le PC Windows

1. Décompresser l'archive complète dans un dossier, sans déplacer seulement le fichier `.cmd`.
2. Double-cliquer sur `INSTALLER_BAZOR_VEILLE_1_CLIC.cmd` dans ce dossier. Le programme vérifie Python, une installation BAZOR connue et l'absence de la tâche `BAZOR\BilanDemarrage`. Il ne crée pas de deuxième veille si cette tâche existe.
3. Attendre que `Documents\BAZOR\rapport_demarrage_dernier.txt` apparaisse. La fenêtre compacte « BAZOR — veille des projets » s'ouvre après l'inventaire.
4. Redémarrer Windows normalement, puis ouvrir le nouveau rapport dans la même fenêtre. `OUVRIR_BAZOR_VEILLE.cmd` rouvre la fenêtre si elle a été masquée. Fermer la fenêtre avec `X` la masque et laisse le journal Studio en service.

La veille s'installe pour le compte Windows actuel et démarre **à l'ouverture de session** avec `pythonw.exe`. Elle ne demande pas d'administration, ne lance pas de modèle, ne change pas les services et ne fait aucun appel IA payant. Les sous-contrôles sont isolés : un échec d'antivirus ou de lecture du registre est mentionné dans le rapport et les suivants continuent. Un rapport horodaté JSON et texte est enregistré à chaque ouverture de session dans `Documents\BAZOR`. Le journal continu `Documents\BAZOR\Studio\journal.jsonl` relève les jobs, prompts, vignettes disponibles, erreurs renvoyées par les API Studio/ComfyUI et les fichiers log locaux. Les journaux restent sur ce PC.

La console du **navigateur** et les fenêtres de commande déjà lancées ne peuvent pas être interceptées ou masquées rétroactivement par cette veille. Une erreur qui n'existe que dans la console du navigateur nécessitera une modification de l'interface Studio à partir de son code installé. Les vignettes vidéo demandent une sortie achevée et un `ffmpeg` déjà présent. Aucune qualité vidéo n'est garantie par la seule veille.

Si l'observateur Studio déjà fourni avec BAZOR écrit un `latest.json` récent dans le même dossier, la fenêtre compacte réutilise son état et évite de sonder les mêmes jobs une seconde fois.

Le rapport distingue « répond sur son port », « fichier présent », « déclaré installé » et « usage réel dans BAZOR ». La présence d'un modèle Ollama ou d'une application ChatGPT ne prouve pas qu'elle est appelée par BAZOR. L'inventaire des processus est un instantané après connexion, complété par les entrées de démarrage et les événements antivirus accessibles.

Pour retirer la veille : `RETIRER_BAZOR_VEILLE.cmd`. L'entrée de démarrage est supprimée et l'instance s'arrête ; les rapports restent dans Documents. La veille refuse de retirer une entrée qui ne pointe pas sur son propre fichier.
