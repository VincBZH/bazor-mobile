# BAZOR — règle micro-extensions Chrome / Opera et agents temporaires

Version : **1.0.0**
Date : **2026-10-06**
Statut : **RÈGLE TRANSVERSE**

## Objet

Cette règle s'applique à tout micro-outil ou extension Chrome / Opera créé dans l'écosystème BAZOR, qu'il soit durable ou temporaire.

Le principe est double :
1. réutiliser et proposer les micro-extensions existantes quand une situation analogue réapparaît ;
2. détecter les suites répétitives d'opérations navigateur et, avec l'accord de Vincent, les transformer progressivement en automatisation locale pilotée par BAZOR + Ollama.

## 1. Réutilisation et suggestion par analogie

BAZOR, GPT ou un agent doit rechercher une analogie avec les micro-outils déjà connus lorsqu'il observe :

- plusieurs onglets ou services utilisés pour un même objectif ;
- des va-et-vient répétés entre onglets ;
- des séquences récurrentes du type copier → changer d'onglet → coller → envoyer → attendre → récupérer → recopier ;
- les mêmes clics, formulaires, imports, téléchargements ou changements d'état répétés ;
- une coordination multi-conversations / multi-agents ;
- un besoin de suivi visuel d'état, de séquencement ou de reprise.

Si une extension existante couvre déjà tout ou partie du besoin, elle doit être proposée en priorité avant d'en créer une nouvelle.

Si aucune extension ne correspond exactement mais qu'une combinaison de fonctions revient, BAZOR doit proposer une **organisation par micro-extension** ou une extension composite minimale au lieu d'ajouter des manipulations manuelles supplémentaires.

La proposition doit rester contextuelle : pas de suggestion systématique hors besoin réel.

## 2. Observation d'une séquence : autorisation obligatoire avant journalisation

Avant toute observation détaillée d'une séquence utilisateur, BAZOR ou l'agent doit demander une autorisation explicite de journalisation.

Formulation conseillée :

> Je vois une séquence répétitive entre plusieurs onglets. M'autorises-tu à journaliser localement les étapes pendant quelques cycles pour comprendre le mécanisme et te proposer une automatisation ?

Par défaut, l'autorisation vaut pour une **session courte et limitée au workflow visé**.

### Ce qui peut être journalisé après accord

- ordre des onglets / domaines ;
- clics et actions structurantes ;
- changements d'état ;
- copier/coller sous forme de métadonnées ou contenu utile si nécessaire au workflow ;
- temps d'attente ;
- déclencheurs et résultat final ;
- erreurs et reprises.

### Exclusions obligatoires

Même avec une autorisation large, ne jamais journaliser ni conserver volontairement :

- mots de passe ;
- codes MFA / OTP ;
- jetons d'authentification ;
- secrets API ;
- données bancaires complètes ;
- champs de type mot de passe ;
- contenu privé sans rapport avec le workflow ;
- navigation privée / incognito, sauf mécanisme séparé explicitement autorisé et conçu pour cela.

Les données de journalisation sont **locales par défaut**, stockées sous `Téléchargements\BAZOR AI\Logs` ou un sous-dossier du projet, avec durée de rétention courte. Une fois le modèle de séquence compris et validé, les traces brutes doivent être supprimées ou réduites à une recette abstraite, sauf demande contraire de Vincent.

## 3. Détection de motif répétitif

Une séquence devient candidate à l'automatisation quand BAZOR détecte plusieurs occurrences suffisamment similaires d'un même cycle d'opérations.

Le moteur doit chercher une structure stable :

`ENTRÉE -> ACTIONS -> ATTENTE/CONDITION -> RÉSULTAT -> TRANSFERT -> ÉTAPE SUIVANTE`

Exemples :

- onglet A : copier une réponse ;
- onglet B : coller, envoyer, attendre ;
- onglet B : récupérer le résultat ;
- onglet C : coller le résultat ;
- recommencer.

Il ne faut pas automatiser sur une seule occurrence ambiguë. Avant automatisation, le système doit connaître :

- le **but à atteindre** ;
- les entrées variables ;
- les étapes stables ;
- les conditions d'attente ;
- le critère de réussite ;
- les erreurs récupérables ;
- les points où une confirmation humaine reste nécessaire.

## 4. Création d'un agent temporaire BAZOR + Ollama

Une fois le principe compris et le but confirmé, BAZOR peut proposer de créer un **micro-agent temporaire local** chargé de ce workflow.

Ce micro-agent :

- utilise BAZOR pour l'orchestration, les permissions, l'état et les preuves ;
- utilise Ollama local pour l'analyse légère, le classement, la compréhension des variations et les décisions bornées ;
- ne possède que les permissions nécessaires au workflow ;
- dispose d'une machine d'état explicite ;
- journalise ses actions importantes ;
- prévoit pause, reprise, annulation et reprise manuelle ;
- s'arrête sur erreur répétée, état incohérent ou changement de page non reconnu ;
- n'exécute aucun shell arbitraire provenant d'une page web ;
- ne s'étend jamais de lui-même à d'autres sites ou tâches.

Le micro-agent doit être **temporaire par défaut** : il disparaît ou est archivé lorsque le workflow est terminé, sauf si Vincent décide d'en faire un outil permanent.

## 5. Passage de l'agent temporaire à une micro-extension permanente

Si le même workflow est réutilisé et suffisamment stable, BAZOR doit proposer de le convertir en micro-extension Chrome / Opera permanente.

La conversion doit réutiliser :

- la recette de séquence validée ;
- les sélecteurs / règles de détection utiles ;
- les garde-fous ;
- les tests ;
- la configuration ;
- les permissions minimales.

L'extension résultante doit être enregistrée dans l'Encyclopédie et le registre BAZOR avec version, but, permissions, compatibilité navigateur, limites, tests et règles de proposition.

## 6. Registre obligatoire de chaque micro-extension

Chaque micro-extension créée doit déclarer au minimum :

- `id` ;
- nom et version ;
- Chrome / Opera / les deux ;
- objectif ;
- déclencheurs de proposition ;
- permissions navigateur ;
- domaines visés ;
- données locales créées ;
- mode de journalisation ;
- statut de validation ;
- limites connues ;
- artefact et hash si packagé ;
- possibilité de désactivation / suppression.

## 7. Prochaine étape : empaqueteur automatique d'extensions

Le prochain composant à construire est **BAZOR Extension Packer**.

But : prendre un dossier de micro-extension validé et produire automatiquement un livrable propre pour Chrome / Opera avec :

- validation `manifest.json` ;
- contrôle des permissions ;
- contrôle syntaxe JS/JSON ;
- vérification des fichiers référencés ;
- génération des icônes/manifeste si prévu par le projet ;
- numéro de version ;
- ZIP reproductible ;
- SHA-256 ;
- fiche Encyclopédie / Registry ;
- rapport de tests ;
- option d'installation locale guidée ;
- refus d'empaqueter si un test obligatoire échoue.

L'empaqueteur ne doit pas publier automatiquement sur un store sans accord explicite.
