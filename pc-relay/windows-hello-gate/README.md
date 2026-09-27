# BAZOR : porte locale Windows Hello — prototype, pas encore un installateur

Cette brique appartient au **Pont et au Hub existants**. Elle n'installe pas un troisième BAZOR et n'est pas branchée à l'agent V2 en production.

## Livré maintenant

- `pc-relay/bazor_action_policy.py` : politique de droits locale, uniquement pour des **diagnostics typés** ; session maximale de 15 minutes ; refus de toute opération inconnue, demande GitHub directe, commande shell, accès payant ou déploiement ; perte des droits si Windows se verrouille ; PANIC et refus Hello.
- `pc-relay/windows-hello-gate/` : programme Windows Forms qui utilise la vraie API **`UserConsentVerifierInterop.RequestVerificationForWindowAsync(hwnd, ...)`**, adaptée aux applications Windows desktop. PIN/biométrie restent dans l'interface Windows. Pas de champ mot de passe, de collecte de clé, de service Internet ni de port ouvert.
- Un test de santé limité à trois URL HTTP **fixes** de `127.0.0.1` (Core 8775, Room 8765, Ollama 11434). Un HTTP 200 n'est affiché que comme **joignable**, pas comme identité ou fonctionnalité certifiée.
- Échéance après 15 minutes, interdiction immédiate de nouvelles vérifications après PANIC ou verrouillage de la session Windows. Les appels déjà partis ne peuvent pas toujours être annulés au niveau du réseau ; aucune opération destructive n'existe dans le prototype.

## Télécharger et tester le prototype (facultatif)

Le workflow GitHub Actions sur Windows compile un exécutable **autonome pour Windows x64**, puis publie un artefact `BAZOR-Hello-Diagnostics-PROTOTYPE-win-x64`, conservé **7 jours**. Extraire son ZIP et lancer `BazorHelloGate.exe` depuis le dossier extrait. Cette version **n'est pas signée par un éditeur**, Windows SmartScreen/antivirus peuvent donc la signaler ; ne contournez pas une alerte de sécurité sans avoir vérifié la provenance. L'artefact est lié directement au commit de cette branche et à son workflow. Aucun `dotnet` ni Python requis pour ce prototype autonome.

Pour tester : cliquer sur « Autoriser les diagnostics », valider la véritable boîte de dialogue Windows Hello ; cliquer sur « Vérifier Core / Room / Ollama » ; vérifier que PANIC désactive immédiatement l'action ; refaire après verrouillage de Windows et expiration. Le texte « joignable » ne certifie pas l'identité d'un serveur. Aucun changement de programme local n'est réalisé.

**Ce prototype ne remplace pas le Pont V2 et ne permet pas d'autoriser les mises à jour de programmes.** Le vrai test Windows Hello interactif n'est pas possible sur un runner CI sans session utilisateur ; il doit être effectué localement et ses résultats techniques assainis doivent être conservés.

## Prochaine intégration sans copier-coller

Pour franchir la porte des diagnostics aux opérations de code, le composant de politique doit être appliqué **dans le service qui exécute les actions**, et non dans une case JSON du navigateur ni dans un code de sortie de programme susceptible d'être remplacé.

La liaison Hub–service devra utiliser une IPC locale à droits restreints et une preuve authentifiée, avec session courte, liaisons à l'identité utilisateur et au périmètre de projets, révocation à verrouillage et PANIC. Avant toute modification de fichiers : opération **typée et listée**, projet/répertoire autorisé, examen du plan, sauvegarde restituable, essais sur staging, validation Hello supplémentaire pour actions sensibles, et rollback. Les demandes reçues depuis GitHub ne doivent jamais contenir de shell exécutable ni élargir les droits de l'agent.

**État réel :** noyau de politique et UI Hello compilés et testés hors PC ; pas d'IPC authentifiée complète ; pas de permission d'écriture ni d'autonomie multi-IA. Les tests Python emploient un faux vérificateur Hello pour valider les refus : ce n'est PAS une preuve de succès de l'appareil Windows Hello.

Référence Microsoft : https://learn.microsoft.com/en-us/uwp/api/windows.security.credentials.ui.userconsentverifier?view=winrt-26100
