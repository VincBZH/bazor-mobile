# BAZOR-RUNTIME-SILENT-AUTOFIX-V1.0.0

- Version : `1.0.0`
- Date : `2026-10-06`
- Statut : `READY_FOR_LOCAL_RUN`
- Objet : audit et correction réversible des consoles BAZOR/Ollama visibles et des lancements BAZOR au démarrage Windows.
- Paquet : `BAZOR_RUNTIME_SILENT_AUTOFIX_V1_0_0.zip`
- SHA-256 du paquet : `d42a714332fcd6bd643c9c497fb5f2427c4d8e6fc3cf35489183a8eba3b0756e`

## Principes

- Audit live du PC avant toute modification : Startup, Registry Run/RunOnce, tâches planifiées BAZOR, ports locaux connus et consoles visibles.
- Ollama local est utilisé uniquement comme auditeur/classificateur ; aucune commande shell produite par le modèle n’est exécutée.
- Actions fermées : `KEEP`, `KEEP_HIDDEN`, `DISABLE_STARTUP`, `REVIEW`.
- Les consoles identifiées sont masquées, jamais tuées.
- Les tâches planifiées sont auditées mais ne sont pas réécrites automatiquement.
- Les changements Startup/Registry sont sauvegardés et réversibles.
- Les composants tiers non BAZOR sont hors périmètre.
- Les journaux locaux sont écrits dans `Downloads\BAZOR\Logs` et `Downloads\BAZOR AI\_SYSTEM\RuntimeGuard`, jamais dans Documents/OneDrive.

## Traçage après exécution locale

Le run réel écrit son rapport, son manifest de rollback et ses tags dans le RuntimeGuard. Si l’Encyclopédie locale est présente, une note du même tag est ajoutée à son dossier `vault\changes`. Cette fiche GitHub documente la livraison ; elle ne prétend pas que le correctif a déjà été appliqué sur le PC.
