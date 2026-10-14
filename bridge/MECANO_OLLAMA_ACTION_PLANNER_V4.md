# BAZOR Mécano — propositions structurées Ollama (prototype V4)

## Pourquoi
La mission locale CONTROL-P0-001 (GitHub #206) s'est arrêtée avec
"exactly_one_action_required". Il n'y avait aucune modification, et pas de
diagnostic du nombre d'actions. La correction chirurgicale V3 et son smoke
test #208 ont été validés séparément ; ce composant ne les remplace pas.

## Fonctionnement
Le module \`pc-relay/bazor_ollama_action_planner.py\` fournit une primitive
strictement encadrée \`run_bounded_task(core_task, action_engine, scope, read_bytes)\`.

- La mission vient d'une **liste locale approuvée**, jamais du corps d'un ticket GitHub.
- \`provider="ollama"\`, \`apply_actions=False\` lors de la proposition. Le Core
  rapporte le moteur et le modèle réellement utilisés.
- Une proposition non conforme autorise **un seul nouvel essai**, avec un code
  d'erreur assaini (pas de contenu de réponse réinjecté).
- On refuse toute opération hors du fichier, racine et type d'action inscrits
  dans \`ActionScope\`; pour \`replace\`, l'empreinte SHA-256 initiale est obligatoire,
  ainsi que les textes attendus si fournis par le cahier des charges local.
- Toute écriture passe ensuite **une fois au maximum** par \`ActionEngine.apply\`
  avec sandbox, sauvegarde, tests déterministes et rollback.
- La réponse d'exécution n'expose que l'état, le nombre d'essais et d'actions,
  le nombre de fichiers, tests et la cause assainie; aucun contenu privé.

## Intégration prévue
Le Watcher déjà en place sur Windows inclut des protections locales différentes
de la branche GitHub main. N'effectuer **aucune synchronisation git** ni copie
aveugle du Watcher pour installer ce module.

Après inspection de l'empreinte SHA-256 locale :
1. Copier le nouveau module dans \`pc-relay\` avec sauvegarde hors dépôt.
2. Dans le gestionnaire existant des tâches locales, autoriser explicitement
   un nouvel identifiant approuvé et une seule cible connue.
3. Construire \`ActionScope\` avec la racine/cible/empreinte réellement lue et des
   gardes de contenu liés à la correction approuvée.
4. Passer \`_core_task\` et l'instance existante de \`ActionEngine\`.
5. Rapporter les champs assainis, ne jamais publier la réponse brute d'Ollama.
6. Tester une erreur zéro action suivie d'une réponse valide, une modification
   refusée, un refus de fournisseur et un vrai test Windows réversible.

## Preuves / limites
\`python -m unittest -v pc-relay/tests/test_bazor_ollama_action_planner.py\`
14 tests unitaires hors ligne (Core / ActionEngine simulés). Ils ne démontrent
ni mise à jour du PC, ni succès sur une vraie correction BAZOR.

**Statut : CODE PREPARÉ SUR BRANCHE, NON INSTALLÉ SUR WINDOWS.**
Ne pas publier de nouvelle mission automatique tant que l'intégration locale
et les tests de sûreté n'ont pas réussi.
