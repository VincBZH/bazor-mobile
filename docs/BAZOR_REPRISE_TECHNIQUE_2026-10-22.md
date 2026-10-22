# BAZOR — Reprise technique vérifiée (22 octobre 2026)

> Rapport de continuité compilé à partir des échanges et journaux transmis dans ChatGPT. **Ce document n'est pas la preuve d'une exécution actuelle sur le PC.** Il distingue essais observés, déclarations issues d'autres sessions et éléments non validés.
>
> Périmètre : BAZOR CINÉMA, pont NoTrack/Chrome, BAZOR Night, Mécano, Ollama, Mammouth et production vidéo. Aucun secret, cookie, jeton, média personnel ou scénario intégral n'est publié ici.

## Résultats établis

| Sujet | Preuve rapportée/observée | État |
|---|---|---|
| NoTrack DOM | Diagnostics successifs : 1 message utilisateur, 1 assistant, 1 compositeur et 1 bouton | **PASS** sur discussion de test |
| Calibration NoTrack | Calibration manuelle des deux dernières bulles; `DIAGNOSTIC_OK` après `MESSAGE_ROLE_UNVERIFIED` | **PASS** ponctuel |
| Activité NoTrack | Correction de détection limitée à la conversation; diagnostic ensuite OK | **PASS** ponctuel, à surveiller |
| Transmission test Chrome | Tentative `BAZOR_1792639246450`, événement `SEND_ACCEPTED`; capture NoTrack montrant demande/réponse de test | **PASS** pour échange visible |
| Confirmation automatique | `REVIEW / ACTIVITY_NOT_OBSERVED`, aucun `COMPLETE` | **NON VALIDÉ** |
| Protection anti-doublon | État `REVIEW`, ne pas relancer sans rapprochement | **À PRÉSERVER** |
| Installation extensions | Journaux `installed:true`, sauvegardes créées; manifeste et worker Night inchangés sur les corrections ultérieures | **PASS** pour installations rapportées, pas test de Night |
| CINÉMA | Port historique local 18987, build déclaré `bazor-cinema-v1-1-beta-20261014-r2`; 2 jobs `simulation` terminés | **PAS DE FILM RÉEL PROUVÉ** |
| Ressources | Derniers diagnostics : RAM libre ~1,03–1,37 Gio, seuil affiché de 2 Gio, mémoire de pic non certifiée | **BLOQUÉ RENDU** |
| Mammouth ↔ BAZOR | Selon le bilan d'une autre conversation, Claude a appelé `bazor_status` via pont HTTPS éphémère; fermeture du Funnel signalée | **RAPPORTÉ, NON REVÉRIFIÉ ICI** |
| Night, Mécano, Watcher, FileBus, Ollama autonome | Existence et versions historiques mentionnées; aucune supervision nocturne active confirmée dans cette session | **NON CONFIRMÉ** |

## Chronologie utile du pont NoTrack

1. V3.2.13 R2 : installation après correction du groupe `content_scripts` vide dans le manifeste.
2. DOM Audit V1 : les rôles restaient indétectables (0 utilisateur, 0 assistant), deux zones de saisie.
3. Cartographie DOM V2 : bulles `.bubble` identifiées sous `MAIN`; un seul compositeur pertinent sous `MAIN > FORM`.
4. Calibration rôles V3.1 : l'utilisateur désigne son message puis celui de NoTrack; obtention de `users:1, assistants:1`.
5. Correctif `GENERATION_ACTIVE` : limitation des signaux d'activité aux zones de conversation et de saisie.
6. Observation d'envoi V1 : clarification des refus locaux; diagnostic périmé après 30 s, absence de consigne détectée, sans tentative.
7. Test envoyé : `SEND_ACCEPTED` et réponse de test affichée côté NoTrack; `REVIEW / ACTIVITY_NOT_OBSERVED` faute de preuve machine de la phase de génération. **Ne pas transformer REVIEW en COMPLETE sur la seule base d'une réponse visible.**

## Objectif prioritaire réel

Produire une vidéo **d'environ 60 secondes** montrant un même personnage féminin dans un hôtel puis sa chambre, avec continuité visuelle et scénario fourni conservé sans réécriture non demandée.

**Plan d'essai borné :**
1. Identifier le moteur CINÉMA et le workflow ComfyUI réellement actifs; vérifier poids et compatibilité du GPU.
2. Préflight RAM, VRAM, disque, processus : ne tuer aucun processus utilisateur, ne pas forcer un rendu si les seuils sont insuffisants.
3. Vérifier un clip court neutre et le média de référence autorisé, puis continuité entre clips et assemblage. Tout fichier vidéo final doit être décodable et inspectable; conserver originaux/paramètres.
4. Si vidéo non réalisable : créer **une alpha CINÉMA simplifiée**, en copie isolée avec choix image, scénario, lancer/annuler, progression, sortie et journal; pas de création fictive de vidéo.

## Travail autonome et priorités

- Réutiliser Mécano, Watcher, FileBus, bridge et Ollama **seulement après preuve de présence et de fonctionnement**.
- Tâches légères déterministes sans LLM; Ollama local si sain. Codex ou Mammouth seulement par connexions et crédits existants réellement vérifiés; **pas de bascule magique entre abonnements** ni exploitation de cookies UI.
- Aucune dépense, aucun fournisseur cloud/API payé, aucune modification du pare-feu, aucun service permanent ou modification production sans autorisation spécifique.
- Travail isolé, sauvegarde, rollback, limites de temps et tentatives, journaux et états PASS/FAIL/BLOCKED/NOT_RUN.
- L'utilisateur peut être absent : ne pas déclarer le travail nocturne actif parce qu'une mission a été rédigée. Il faut journaux horodatés montrant tâches prises/exécutées et sorties.

## Documents et liens de contexte communiqués

Ces liens sont **références à consulter**, pas des preuves que leur contenu intégral a été ingéré :

- https://chatgpt.com/share/6ad98456-8648-83eb-a6cc-891ac7fdaaa1
- https://chatgpt.com/share/6ad98484-17c8-83eb-b71f-51e07c99f15e
- https://mammouth.ai/shared/7967caab-9163-43aa-b38b-0aac39c9a0c0
- https://mammouth.ai/shared/2f6d70c8-01fb-4aff-ac6b-91bff4ffa712

## Critères de validation à venir

- [ ] Audit local horodaté du superviseur et des services : preuves des missions nocturnes réellement démarrées.
- [ ] Workflow ComfyUI exécutable identifié, RAM/VRAM/disque suffisants.
- [ ] Clip vidéo réel décodable, puis enchaînement et assemblage ~60 secondes.
- [ ] À défaut, alpha CINÉMA plus simple exécutée et testée localement.
- [ ] Échange NoTrack reconnu automatiquement de bout en bout sans doublon; le pont ne doit pas monopoliser les efforts tant qu'il n'est pas bloquant pour le film.

**À ne pas confondre :** `SEND_ACCEPTED` = demande acceptée par le pont, pas confirmation garantie du cycle; `COMPLETE` absent. Deux jobs de simulation ne démontrent pas la génération d'une vraie vidéo.
