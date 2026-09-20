# Studio Session S2.2 — transmission aux entités BAZOR

Sources candidates disponibles pour GPT, Ollama, Mammouth et BAZOR Core. Lire [le compte rendu](fix/README.md) et [le handoff machine](HANDOFF.json) avant toute reprise.

- [Archive complète : sources, installateur, tests et logs](BAZOR_STUDIO_SESSION_S2_SOURCES.zip)
- [Installateur un clic](BAZOR_STUDIO_SESSION_S2_1_CLIC.cmd)
- [Sources du correctif lisibles](fix/)
- [Preuves locales et limites](VERIFICATION.json)
- [Empreinte archive](SHA256SUMS)

Les contrôles GitHub testent le paquet exact sous Linux et le helper d'arrêt isolé sous Windows. Les interactions Windows sont simulées : aucun résultat CI ne vaut génération GPU ni acceptation UAC sur le PC. Aucun statut de tâche du registre n'est passé à DONE et aucun déploiement n'est déclenché par cette transmission.

Prochain travail : comparer avec le Studio réel via l'Action Engine existant, conserver les hotfix UI/API et le garde-fou mémoire, valider l'installation puis un rendu neutre image et vidéo. Fournir fichiers/hashes, modèles, workflow réel, résultat média, analyse et blocages au coordinateur GPT.
