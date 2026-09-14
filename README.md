# BAZOR Mobile / AI ROOM

BAZOR Mobile se connecte au PC par un relais local sécurisé.

## BAZOR API v1

- Détection mobile : UDP 8766
- API locale : HTTP 8765
- Santé : `GET /api/v1/health`
- Modèles : `GET /api/v1/models`
- Chat : `POST /api/v1/chat`
- Ollama reste lié à `127.0.0.1:11434` sur le PC : il n'est jamais exposé au téléphone.
- Aucune commande shell n'est acceptée par l'API.
- Les requêtes non locales sont refusées.

## Démarrage PC

Lancer :

`pc-relay/DEMARRER_BAZOR_PC_RELAY.cmd`

L'APK détecte automatiquement le PC sur le Wi-Fi puis utilise BAZOR API.

## Routage

- OLLAMA : fonctionnel via BAZOR API.
- GPT : route API prévue, connecteur GPT côté PC encore à configurer.
- LES DEUX : Ollama répond déjà ; GPT sera ajouté au même point d'entrée.

