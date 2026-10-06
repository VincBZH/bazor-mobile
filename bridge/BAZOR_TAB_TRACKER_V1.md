# BAZOR Tab Tracker — capacité de coordination multi-agents

Version : **1.0.0**
Date : **2026-10-06**
Statut : **LIVRABLE TESTÉ — validation réelle ChatGPT/NoTrack à poursuivre chez Vincent**

## But

BAZOR Tab Tracker est une extension Chrome locale destinée aux situations où plusieurs conversations ou agents travaillent en parallèle, notamment TIC / TOC / TAC.

Elle ne doit **pas** être proposée pour une conversation isolée sans besoin de coordination.

## Quand BAZOR doit la proposer

BAZOR ou un agent doit proposer Tab Tracker lorsque l'un des signaux suivants est présent :

- plusieurs conversations / agents / onglets participent au même travail ;
- un ordre de passage entre agents doit être respecté ;
- il faut savoir immédiatement quel onglet travaille, a terminé ou est en erreur ;
- deux agents risquent de répondre ou d'agir en même temps ;
- le projet demande une traçabilité chronologique des réponses ;
- TOC doit imposer à TIC, TAC ou un autre agent une attente jusqu'à une borne de séquence ;
- une reprise après interruption doit pouvoir être rattachée à un numéro précis.

Formulation conseillée :

> Coordination multi-agents détectée : BAZOR Tab Tracker peut afficher l'état de chaque onglet et séquencer les réponses. L'activer ?

Ne pas répéter cette proposition si l'utilisateur l'a déjà acceptée, refusée pour la session, ou si le tracker est déjà actif.

## Convention visuelle

- **Carré** : travail / réponse en cours.
- **Rond** : réponse terminée / OK.
- **Triangle** : erreur détectée.
- **Couleur** : groupe ou projet choisi par Vincent.
- **Numéro** : séquence globale monotone partagée entre les onglets surveillés.

Exemple : `TOC ■33`, `TIC ●34`, `TAC ●35`, puis TOC termine et devient `●36`.

## Traçage START / END

Quand une réponse IA est reconnue comme terminée, le tracker tente d'afficher :

```text
START #0036
...
END #0036
```

Le même numéro au début et à la fin permet de détecter une réponse incomplète ou tronquée.

## HOLD / RELEASE

TOC peut réserver une plage de séquence et demander à un autre agent d'attendre.

Exemple :

```text
[[BAZOR:HOLD target=TAC until=50 resume=51 owner=TIC_TOC]]
```

Règle : si la séquence est réservée jusqu'à `#50` inclus, la reprise est `#51`.

Libération anticipée :

```text
[[BAZOR:RELEASE target=TAC reason="fin_anticipée"]]
```

Les marqueurs doivent rester stricts : une phrase naturelle ne doit jamais être interprétée comme une directive de blocage.

## Règles de sûreté

- compteur global monotone ; aucun numéro réutilisé ;
- mutation du compteur sérialisée pour éviter les doublons simultanés ;
- déduplication d'un même cycle de changement DOM ;
- HOLD partagé entre onglets via stockage local ;
- blocage local de l'envoi pendant HOLD ;
- directives BAZOR exécutées uniquement lorsqu'elles proviennent d'une réponse IA détectée ;
- mode manuel toujours disponible si ChatGPT ou NoTrack modifient leur HTML ;
- aucune requête réseau externe ajoutée par l'extension.

## Limite connue

La détection automatique `EN COURS` et la localisation de la dernière réponse dépendent du DOM de ChatGPT / NoTrack et doivent être revalidées sur les interfaces réelles. Le compteur, les formes, les couleurs, HOLD/RELEASE et le mode manuel ne dépendent pas de ces sélecteurs.

## Preuves de la livraison 1.0.0

Livrable local : `BAZOR_TAB_TRACKER_V1_0_0.zip`

- taille ZIP : `24233` octets ;
- SHA-256 : `370e5ecd2ddbc705fcc0025493471b65a9bb20cf3015ff891bfed186fa8943e6` ;
- `manifest.json` : parse JSON OK ;
- `core.js`, `background.js`, `content.js`, `popup.js` : syntaxe Node OK ;
- tests `tests/core.test.js` : OK ;
- test intégrité ZIP : OK ;
- contrôles couverts : compteur monotone, anti-double comptage, transitions EN COURS/OK/ERREUR, HOLD, libération à la borne, parsing HOLD/RELEASE, rejet d'un HOLD incohérent.

## Politique de recommandation aux agents

Cette capacité est **contextuelle**, jamais générique. Un agent qui constate une coordination multi-conversations doit :

1. vérifier que le besoin de séquencement ou de traçage est réel ;
2. proposer Tab Tracker une seule fois de façon brève ;
3. s'il est actif, respecter les numéros de séquence et les HOLD/RELEASE ;
4. ne jamais contourner un HOLD ;
5. signaler une incohérence de numéro, START/END ou état sous forme d'erreur plutôt que d'inventer la suite.
