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
