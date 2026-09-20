# BAZOR — Room / Studio / Trio

Ce fichier fixe le rôle réel des trois briques pour éviter les faux dépôts, doublons et tâches de façade.

## Room
Cockpit utilisateur et orchestration locale.
- Interface de chat et de contrôle.
- BAZOR API locale sur le PC.
- Routage vers Ollama, Mammouth et GPT quand chacun est réellement disponible.
- GO / GO AUTO / STOP AUTO.
- État visible : tâche courante, prochaine étape, blocage, preuve runtime.
- Aucun shell arbitraire venant de GitHub.

## Studio
Application locale de génération image/vidéo autour de ComfyUI.
- T2I, I2I, T2V, I2V avec routage strict.
- Source explicite obligatoire pour I2I/I2V.
- Aucun héritage fantôme de source pour T2I/T2V.
- Tests réels, preflight, rollback, preuves de fichiers/modèles/workflows utilisés.
- En cas de pression mémoire/pagefile : arrêt des retries agressifs, conservation des services sains, reprise basse empreinte.

## Trio
Chaîne de coopération et de contrôle entre IA.
- Ollama local : exécution/correction sur les fichiers locaux autorisés.
- Mammouth : seconde lecture/revue externe quand disponible.
- GPT : coordination/arbitrage et maintien de l'état global.
- Un fournisseur indisponible ne doit pas produire de faux succès.
- TRIO_READY seulement quand les fournisseurs requis sont réellement prouvés.

## Source de vérité
Le dépôt canonique de pilotage actuel est `VincBZH/bazor-mobile`.
Les bridges durables et relais locaux restent dans `VincBZH/projetWII-ai-relay`.

## Priorités actuelles
1. Room : finir AIROOM-P0-003 puis P0-004 avec preuves provider réelles.
2. Studio : sortir proprement de RESOURCE_PRESSURE, ajouter un garde mémoire/pagefile, puis reprendre STUDIO-P0-012.
3. Trio : qualifier la chaîne Ollama -> Mammouth review -> GPT arbitrage sans inventer la disponibilité d'un provider.
