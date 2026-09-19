# BAZOR FILEBUS V1

But: permettre à GPT, Ollama local et Mammouth de communiquer via des fichiers GitHub synchronisés localement, sans transformer GitHub en terminal distant.

## Déclencheurs sûrs
- [bazor-filebus:ollama:<fichier>]
- [bazor-filebus:mammouth:<fichier>]

Le watcher n'accepte que des fichiers sous bridge/messages/ avec un nom simple [A-Za-z0-9._-].
Il lit le fichier local synchronisé puis transmet son contenu au moteur demandé.
Aucune commande shell, aucun eval, aucun chemin arbitraire.

## Format attendu
Chaque message doit se terminer par un bloc RESPONSE_FORMAT et une instruction NEXT.
Les réponses reviennent dans le commentaire GitHub de l'issue déclencheuse.

## Règle projet
Ce canal est global à tous les projets BAZOR. Les fichiers doivent toujours préciser PROJECT, REQUEST_ID, STATUS attendu, NEXT et les preuves nécessaires.

## MODE AUTONOME — ZÉRO COPIER-COLLER HUMAIN

Objectif: Vincent ne sert plus de relais manuel entre GPT, Ollama, Mammouth et BAZOR.

Règles obligatoires:
1. Toute IA qui reçoit une tâche doit publier elle-même le handoff suivant dans GitHub.
2. Si une réponse d'une autre IA est nécessaire, créer/utiliser directement un ticket FileBus ciblé; ne jamais demander à Vincent de copier-coller.
3. GPT lit directement les preuves GitHub, arbitre et publie la suite.
4. Ollama/BAZOR traite localement via watcher + Action Engine et répond dans GitHub.
5. Mammouth répond via watcher/FileBus; si un modèle échoue, utiliser le failover prévu.
6. PASS uniquement sur preuves structurées; sinon BLOCKED avec cause exacte.
7. Après PASS, déclencher automatiquement NEXT si l'action est prédéfinie et autorisée.
8. Après BLOCKED, publier le correctif minimal suivant ou le handoff technique exact.
9. Ne solliciter Vincent que pour une action physique/interactive impossible à automatiser localement (ex. autorisation système, branchement, confirmation visuelle indispensable).
10. Ne jamais demander à Vincent de recopier des logs ou messages déjà présents sur GitHub.

Boucle standard:
GPT -> GitHub/FileBus -> Ollama ou Mammouth -> GitHub -> GPT -> NEXT.

État courant à conserver:
- Core/watcher: validé
- Ollama FileBus: validé
- Mammouth runtime: test strict via projetWII-ai-relay#6
- FileBus global: non validé tant que #6 n'est pas PASS strict
