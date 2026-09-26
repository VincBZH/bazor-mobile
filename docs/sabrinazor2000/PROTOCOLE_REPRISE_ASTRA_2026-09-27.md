# Reprise Astra — protocole de validation Sabrinazor2000

**Auteur :** ChatGPT / GPT-5.6 Sol, coordinateur fonctionnel et contrôle qualité de Vincent.
**Référence :** SZ2000-20260926-2215 · Suivi : https://github.com/VincBZH/bazor-mobile/issues/166
**Créneau demandé :** dès le 27 septembre 2026 à 01 h 21, heure de Paris, uniquement si le quota Work s'est effectivement réinitialisé.
**Statut :** instructions et cas de test préparés, **non exécutés**.

ATTENTION : ce dépôt BAZOR est public et ne contient pas le code source officiel Repères/Sabrinazor2000. N'y publier aucun renseignement personnel ni document confidentiel. Ne pas créer une deuxième application.

## 1. Premier geste d'Astra

- Accéder au VRAI projet Repères/Sabrinazor2000 et relever l'URL du dépôt source, la branche, le commit, la version déployée.
- Identifier les dernières modifications de Mammouth, son build et ses tests : ne pas redévelopper ce qui marche.
- Une V1 officielle et 113 tests automatisés ont été annoncés dans le suivi #166 ; vérifier les preuves, l'étendue réelle et les échecs avant d'annoncer « terminé ».
- Vérifier l'accès de Sabrina au site et au ZIP réels (le site avait été déclaré réservé à Vincent). Aucun lien sandbox ni maquette distincte.

## 2. Priorité P0 — une seule entrée, trois questions

1. « Quel est votre poste ? » Exemple gris en italique : « Agente administrative d'accueil ». L'aide indique de consulter contrat ou fiche de paie.
2. « Quel salaire net recevez-vous chaque mois ? » Exemple gris en italique : « 1 800 € ». L'aide explique la différence entre net habituel et net après prélèvement à la source, et les éventuelles primes.
3. « Depuis quand travaillez-vous ici ? » Exemple gris en italique : « Septembre 2006 ». L'aide précise où retrouver la date d'entrée.

Pour chaque réponse : infobulle précise en langage courant ; « Je ne sais pas » et « Plus tard » ; exemple visuel non enregistré ; sauvegarde automatique. Après trois réponses, synthèse immédiate et rubriques facultatives.

**Tests d'acceptation P0**, avec jeu de données intégralement fictif :
- T01 : dossier vierge → « 0/3 » avec les trois informations manquantes nommées.
- T02 : seul le poste rempli → « 1/3, salaire et entrée manquants » ; fermeture puis reprise conserve le poste.
- T03 : trois réponses → « 3/3 », synthèse visible sans imposer le questionnaire complémentaire.
- T04 : texte d'exemple gris/italique disparaît à la saisie et n'est ni stocké ni exporté.
- T05 : les trois infobulles donnent une reformulation, un exemple et une source possible ; clavier et mobile fonctionnent.
- T06 : modifier salaire ou date d'entrée recalcule TOUTES les simulations et tous les exports dépendants, sans ancien chiffre résiduel.
- T07 : inconnu / vide / montant 0 sont bien distincts ; un champ manquant ne devient jamais 0 €.
- T08 : retour arrière, rafraîchissement, fermeture et réouverture ne perdent pas les informations ni ne créent de doublon.

## 3. P1 — informations supplémentaires entièrement facultatives

Onglet « Compléter mon dossier » replié par défaut : famille/enfants ; logement privé/social, loyer et charges ; salaire, CAF, pension alimentaire directe ou via ARIPA, ASF, autres ressources ; mutuelle, assurances, crédits, carburant, épargne ; ancienneté, RTT (jours/an), télétravail (journées ou demi-journées/semaine), congés et avantages.

- Les questions conditionnelles s'affichent seulement si pertinentes.
- Éviter les doubles comptes : pension reçue via plusieurs canaux et mutuelle déjà retenue sur la fiche de paie.
- Montrer exactement les réponses enregistrées et celles qui manquent, par leur nom.
- Poste réel : cocher ou exclure des tâches proposées à partir de sources professionnelles identifiables ; ajout libre illimité ; validation humaine de toute reformulation IA.
- Documents : fiche de paie, contrat/avenant, attestation CAF, estimation retraite ; import facultatif ET saisie manuelle.

## 4. P1 — « Et si ? » / arguments vérifiables

Quatre simulations : rester, demander des renseignements, préparer une demande de revalorisation, examiner un autre emploi. Présenter montants mensuels/annuels nets, coûts de trajet, avantages, temps et reste à vivre. Séparer clairement fait, hypothèse, déclaration, estimation et droit confirmé.

Le rapport social/financier est un élément contextuel daté, pas une preuve d'un droit individuel à une part de trésorerie. Un écart salarial exige classification, points, ancienneté, quotité, fiche de paie et barème applicable. Offres d'emploi : uniquement des annonces réelles datées et vérifiables. Ne pas annoncer droits CAF, retraite ou fiscalité sans règles récentes et moteur audité.

## 5. P2 — documents et IA du PC distant

Aucun transfert automatique de données privées. Exiger un consentement explicite et informer que le PC de Vincent traitera les documents et qu'il peut y accéder en tant qu'administrateur. Ne pas permettre l'import de dossiers confidentiels de tiers.

Tester d'abord avec des documents fictifs : types/tailles admis, analyse antivirus, connexion authentifiée et chiffrée, file d'attente, durée limitée, effacement et contrôle des erreurs. Ollama doit rester local sur le PC, jamais exposé directement sur Internet. Pour chaque champ extrait par IA : preuve/page du document, incertitude indiquée, correction et validation avant utilisation.

## 6. Rapport et livraison demandés

Produire la liste des modifications, les fichiers concernés, URL dépôt + commit exact, commandes/logs de build, rapport précis des tests réussis/échoués et captures navigateur réelles. Tester l'accès de Sabrina et le téléchargement HTTPS dans Opera. Ajouter un retour facultatif « Quelle question était difficile ? », « Autre idée ? Remarque ? », sans joindre automatiquement son dossier.

Classer chaque fonction TERMINÉ / PARTIEL / NON FAIT / BLOQUÉ. Publier le résultat **dans le vrai projet Repères** puis déposer seulement son lien et les preuves non sensibles dans le suivi central GitHub #166.

**Cet état n'est pas une exécution d'Astra ; sa session Work nécessite une relance réelle après le rétablissement du quota.**
