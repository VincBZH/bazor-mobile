# BAZOR AI ROOM V3 BETA

Status: **BETA EN TEST**

Date: 2026-09-19

## Point d'entrée prévu
- Room: http://127.0.0.1:8765/
- Panneau de contrôle: http://127.0.0.1:8765/control

## Fonctions présentes dans cette bêta
- panneau de contrôle avec heartbeat réel du watcher ;
- bouton **GO — CONTINUE MAINTENANT** ;
- bouton **JE SUIS EN COLÈRE — AUTO TOTAL** ;
- état tâche / mode / dernière action / dernier résultat / dernière preuve ;
- bootstrap contexte/identités ;
- routes /api/status, /api/context, /api/projects, /health ;
- enchaînement de tâches AI ROOM prédéfinies via le Registry ;
- sécurité: aucune exécution libre de shell reçue depuis GitHub.

## État de qualification
Cette build est une **candidate bêta**, pas une release finale.
Le runtime 8765 doit encore être repris proprement puis les preuves P0-002/P0-003/P0-004 doivent passer.

## Règle de sortie bêta
V3 Stable uniquement après:
1. runtime HTTP PASS ;
2. panneau /control PASS ;
3. routage réel GPT/Ollama/Mammouth PASS ;
4. contexte persistant PASS ;
5. fallback PASS ;
6. Registry + Encyclopédie synchronisés ;
7. preuve finale ROOM_CORE_DELIVERED + TRIO_READY.
