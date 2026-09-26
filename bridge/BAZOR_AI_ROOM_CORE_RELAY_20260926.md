# BAZOR AI ROOM — première liaison multiprestataire dans la vraie Room

**Statut :** code préparé sur la branche \`feat/airoom-v24-core-multiia-20260926\`, CI distincte ; **pas encore déployé ni testé sur le PC de Vincent**. Il s'agit de la Room V2.4 existante, pas d'une autre application Router.

## Ce qui est réellement implémenté

- Interface conversationnelle dans la page AI Room : champ unique, destination, bouton Envoyer, résultats lisibles.
- **Ollama** : l'interface appelle uniquement le Core déjà existant sur \`127.0.0.1:8775/api/v1/chat\`, qui appelle Ollama. Un HTTP 200 sans réponse réelle du modèle n'est pas un succès.
- **Mammouth** : appel via le même Core **uniquement après une case d'autorisation pour cet envoi** ; préflight de la configuration et du budget existant dans Core ; profil \`light\` demandé. Un accès configuré ne vaut pas réponse prouvée. Le Core actuellement sur \`main\` peut encore essayer plusieurs profils en cas d'échec ; les garde-fous renforcés de la PR #150 restent nécessaires pour une stricte limitation des appels.
- **Les deux** : premier appel Ollama, puis envoi explicite à Mammouth de la demande et de la réponse Ollama pour relecture. Aucun appel externe si le premier échange local échoue. Toute étape en échec bloque le statut global.
- **GPT et Astra** : texte préparé à copier, **pas d'API ni d'envoi direct présenté comme disponible**. Le GPT principal peut poster/lire les tickets GitHub via le connecteur ; le watcher local existant peut traiter les tickets \`[bazor-queue]\` si le PC, la CLI \`gh\` et le watcher tournent.
- **NoTrack** : API et autorisation encore non vérifiées, donc désactivé. **DuckDuckGo/Tor** : outils de recherche ou réseau, pas des modèles d'IA ; pas de transit automatique, de clé, de documents personnels ni de contournement de sécurité.

## Premier test existant de la chaîne GPT → GitHub → Core → Ollama

Le GPT principal a ouvert le ticket de contrôle [#168](https://github.com/VincBZH/bazor-mobile/issues/168) avec un contenu fictif. Si le watcher existant est lancé sur le PC, il peut lire le ticket et commenter la réponse Ollama via Core. Tant que le commentaire du watcher et les informations sur l'instance et le modèle n'ont pas été vérifiés, la chaîne reste **NON CERTIFIÉE**. GitHub est un transport, pas une preuve de traitement. Le relais Mammouth ↔ Ollama de la PR #150 reste à qualifier sur Windows (issue [#151](https://github.com/VincBZH/bazor-mobile/issues/151)).

## Comment tester sans casser la Room actuelle

Ne pas installer automatiquement cette branche sur le PC. Après CI verte, utiliser une **copie isolée** du dépôt et lancer uniquement la Room V2.4 sur un port libre (par exemple 8768), en laissant la vraie Room 8765, le Core 8775 et Ollama 11434 tranquilles :

\`\`\`cmd
set "BAZOR_ROOM_HOST=127.0.0.1"
set "BAZOR_ROOM_PORT=8768"
set "BAZOR_CORE_URL=http://127.0.0.1:8775"
py -3 room-payload\v2.4\app\room_v2_server.py
\`\`\`

Puis ouvrir \`http://127.0.0.1:8768/\` dans Opera. Ne pas déclencher de Mammouth avant d'avoir vérifié le budget et la politique de repli de Core. Sur un PC arrêté ou si la Room n'est pas démarrée, rien n'est automatiquement lancé.

## Validation exigée avant « livré »

1. CI Room dédiée verte : compilation Python, tests HTTP Core simulé, JavaScript et éléments de l'interface. Aucune API réelle facturée dans cette CI.
2. Essai Windows depuis la Room : vérifier identité et signature du vrai Core, Ollama modèle réel, texte reçu, et reprise de la réponse sans faux voyant vert.
3. Consentement explicite et budget avant premier appel Mammouth réel, puis une preuve d'appel HTTP/model effectif sans divulgation de clé.
4. Échanges GPT/Astra automatiques uniquement après création et validation de leurs **propres connecteurs autorisés** ; ne pas faire croire qu'un copier/coller ou un e-mail déclenche une IA tierce.

**Sabrina :** son application officielle reste Repères publiée par Astra (suivi [#166](https://github.com/VincBZH/bazor-mobile/issues/166)). Aucune pièce ou donnée sensible ne doit transiter par les tickets publics. La dernière livraison et la sécurité de son application sont des projets distincts.
