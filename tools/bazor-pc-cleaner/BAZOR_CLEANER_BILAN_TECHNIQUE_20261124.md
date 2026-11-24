# BAZOR PC CLEANER ULTIMATE — bilan technique

Date : 24 novembre 2026

## Livraison
- BAZOR PC Cleaner 3.8 repris et remplacé par **BAZOR PC Cleaner Ultimate 4.0**.
- Application : `C:\BAZOR\PC_Cleaner\BAZOR_PC_CLEANER.py`.
- Lanceur Bureau Windows (Bureau redirigé vers OneDrive) : `C:\Users\vgour\OneDrive\Desktop\BAZOR_CLEANER.cmd`.
- Le PANIC est un bouton intégré à l’application et n’arrête que le Cleaner.
- Application locale sans Ollama, modèle IA, API ni téléchargement.
- Interface : inventaire avec gain/risque, surveillance du disque, bouton « NETTOYER ET OPTIMISER », bouton PANIC et historique SQLite.
- Périmètre d’effacement volontairement restreint aux caches pip HTTP et NVIDIA régénérables, et aux fichiers temporaires anciens déverrouillés après confirmation. Aucune nouvelle quarantaine.
- Les copies d’archives de distribution Cleaner 3.8 ont été retirées après remplacement validé. Le lanceur historique `NETTOYAGE_PC_MAX.ps1` redirige vers Ultimate; sa source historique est conservée comme fichier texte inerte.
- Menu BAZOR mis à jour : le Cleaner Ultimate remplace l’entrée Deep Cleaner. Les anciens raccourcis Cleaner/PANIC du Hub ont été retirés; le lanceur de référence est celui du Bureau.

## Nettoyage exécuté et mesure réelle
- Espace libre C: juste avant : **29 021 503 488 octets**.
- Cache pip HTTP supprimé définitivement : **4 062 883 680 octets**.
- Cache NVIDIA DX supprimé définitivement : **4 857 856 octets**.
- Cache NVIDIA GL supprimé définitivement : **97 153 octets**.
- Total des fichiers supprimés : **4 067 838 689 octets** (~3,79 Gio).
- Espace libre C: juste après : **33 093 693 440 octets** (~30,82 Gio).
- Hausse mesurée de l’espace libre : **4 072 189 952 octets** (~3,79 Gio). Le petit écart entre fichiers supprimés et espace disque tient aux écritures simultanées du système.
- Une mesure ultérieure, après activité concurrente, indique environ **31,78 Go libres** sur C:; la mesure immédiate avant/après ci-dessus reste la preuve du gain de cette opération.

## Vérifications et protections
- Compilation syntaxique Python et initialisation de l’interface Tk vérifiées; l’application a été lancée réellement.
- ComfyUI portable existant détecté; aucun second ComfyUI n’a été lancé. Le port 8188 n’a pas répondu au contrôle HTTP, donc son fonctionnement n’est pas certifié ici.
- Ollama, modèles IA, Wan 2.2, UMT5, VAE, configurations, ComfyUI portable, WanGP et AI Simple Studio n’ont pas été supprimés ni démarrés par le Cleaner.
- GPU NVIDIA RTX 4060; `nvidia-smi` : pilote 610.62, runtime CUDA 13.3.
- Toolkits CUDA 13.2 et 13.3 observés. Aucun toolkit désinstallé faute de preuve de non-dépendance; le runtime du pilote ne prouve pas qu’un toolkit est inutilisé.
- Les modèles IA actifs/référencés sont protégés; modèles uniques non référencés également conservés faute de preuve. Les deux anciens chemins de fichiers temporaires UMT5 n’étaient pas présents lors du contrôle final; aucune donnée IA supprimée.
- Quarantaine historique observée vide; aucune quarantaine vidée. Processus Ollama/Python actifs identifiés et laissés intacts.
- L’historique local enregistre les suppressions de caches et les archives Cleaner remplacées.

## Limites restantes
- Nettoyage volontairement sûr, gain obtenu ~4,07 Go, inférieur à l’objectif souhaité de 30–50 Go.
- La désinstallation CUDA 13.2 (~4,08 Go installés), les modèles, environnements Python, sauvegardes BAZOR, jeux, archives de projet et autres quarantaines n’ont pas été effacés : leur inutilité n’est pas démontrée.
- Pas de suppression par âge, nom ou taille seuls; aucune tâche planifiée/service inconnu n’a été désactivé.
- Références de l’encyclopédie/Mécano non modifiées en l’absence d’un point d’intégration spécifique vérifié.

## Publication
Le rapport assaini et les sources de l’application sont publiés dans une branche du dépôt public `VincBZH/bazor-mobile` et proposés en revue :
- PR : https://github.com/VincBZH/bazor-mobile/pull/227
- Branche : `feature/bazor-pc-cleaner-ultimate-release-20261124`
