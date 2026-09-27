# Encyclopédie BAZOR — reprise critique au 27 septembre 2026

**Périmètre.** Les dépôts accessibles sont [`VincBZH/bazor-mobile`](https://github.com/VincBZH/bazor-mobile) et [`VincBZH/projetWII-ai-relay`](https://github.com/VincBZH/projetWII-ai-relay). La source officielle Repères/Sabrina est un projet Sites distinct ; le code Studio installé et les documents Mission Locale résident sur le PC ou dans des espaces privés. Cet inventaire compare le code et les décisions disponibles, **pas** l'état présent de tous les processus Windows. Il complète l'[encyclopédie historique](https://github.com/VincBZH/bazor-mobile/blob/main/BAZOR_ENCYCLOPEDIA.md), le [registre](https://github.com/VincBZH/bazor-mobile/blob/main/bazor_registry.json) et le [tableau de reprise #174](https://github.com/VincBZH/bazor-mobile/issues/174). Les dates, ports et chemins sont des repères historiques à confirmer localement.

## 1. Comment lire un statut

| Mention | Ce qui est établi | Ce qui ne suit pas automatiquement |
|---|---|---|
| Source présente | Fichier, commit ou branche récupérable | Installation sur le PC |
| Test simulé ou CI | Cas déterministe passé sur un runner ou une copie | Usage de l'instance réelle et qualité du résultat |
| Sonde locale | Un endpoint précis a répondu au moment du test | Parcours complet, identité de l'agent, capacité à modifier ou livrer |
| Parcours Windows isolé | Chaîne réelle sur services de test temporaires | Bascule et restauration des services de production |
| Livrable | Version unique, critères métier, essai utilisateur et preuve d'accès | Aucun livrable métier n'est certifié par le menu V0 |

Le registre de septembre et certains README emploient « fonctionnel », « READY » ou des pourcentages. Les lire avec le périmètre de leur preuve. Le problème des faux PASS est suivi en [#160](https://github.com/VincBZH/bazor-mobile/issues/160) ; un code retour, une capture, un MP4 ou `HTTP 200` ne suffisent pas.

## 2. Comparaison des dépôts et lieux de vérité

| Ensemble | Source et fonction | Lieu d'exécution ou données | État / décision |
|---|---|---|---|
| `bazor-mobile` | Core `pc-relay/`, watcher GitHub, Action Engine, Room `room-payload/`, Console Hub, Android, Studio scripts, registre et encyclopédie | Core 8775 ; Room 8765 ; Ollama 11434 ; données sous `%LOCALAPPDATA%` | Dépôt de développement principal ; CI et production restent distinctes. |
| `projetWII-ai-relay` | Issues FileBus, `bazor_room_v2`, handoffs Mammouth et pont Wii | GitHub comme transport de texte/preuves ; jeu local `C:\projetWII` cité au registre | Conserver FileBus PC ; le jeu Wii/PC/Switch est suspendu. Ne pas multiplier les Rooms. |
| Repères / Sabrinazor2000 | Véritable source Sites, hors de ces deux dépôts ; `docs/sabrinazor2000/` dans `bazor-mobile` n'est qu'une note de coordination | Site HTTPS, données personnelles séparées | Source reprise au commit `8294d0094e34073ee132831b8d1d84a29b0a00d8`, accès Sabrina et validation métier encore manquants ([#166](https://github.com/VincBZH/bazor-mobile/issues/166)). |
| AI Simple Studio | Application installée hors dépôt ; `console-hub/`, `pc-relay/` et `studio-deliverables/` sont outils, correctifs ou candidats | `C:\AI\SimpleStudioV2` : 8191 ; ComfyUI portable : 8188 ; modèles/GPU | V3.0.5 était ouverte lors d'un test ; une génération exploitable fidèle reste à prouver ([#161](https://github.com/VincBZH/bazor-mobile/issues/161)). |
| Da Bazor | `tools/da_bazor/`, PR [#175](https://github.com/VincBZH/bazor-mobile/pull/175) | Fenêtre locale volontaire ; sondes loopback | Pilote de lecture, navigation et chat local ; pas encore l'automate qui livre tous les projets. |
| Mission Locale | Documents et compte rendu privés, non source du logiciel | Fichier final et export à identifier | Projet documentaire ; aucune pièce nominative sur GitHub. |

**Bases communes :** `bazor_registry.json` définit projets, dépendances et critères ; `BAZOR_ENCYCLOPEDIA.md` explique les choix ; Core filtre les actions ; Action Engine sauvegarde/prévalide ; Room présente la conversation ; GitHub/FileBus conserve demandes et preuves publiables. Le répertoire local, la branche et la version réellement installée doivent être relevés ensemble avant chaque correction.

## 3. Frise des choix et de leurs conséquences

### 13–18 septembre : Mobile, Core et watcher

L'[objectif initial #1](https://github.com/VincBZH/bazor-mobile/issues/1) reliait un Command Center mobile au PC : détection UDP, inbox, capture, chat Ollama via Core et journal. Les premières issues #2–#21 testaient les pings, déconnexions GO, 502 et les chemins USB/Gateway. La bonne intuition était **une chaîne minimale complète avec un résultat et une trace**. Le piège fut de prendre des pings, des statuts Core ou un GO sans travail prouvé pour la réussite d'une tâche. Le transport téléphone ajoute maintenant une fragilité décisive : décision de Vincent du 27/09, **interaction avec téléphone abandonnée pour tous les usages**, car Bluetooth et éloignement provoquent trop de coupures. Les API Core et les tests de preuve restent réutilisables sur PC ; APK mobile, découverte réseau, ADB, BLE et appairage sortent de la feuille de route.

Le watcher GitHub avait pour fonction de donner au PC des tâches typées et de retourner des preuves. Sa règle utile est qu'une issue n'est jamais une commande shell. Les longues séquences de retries Studio et Room (#85–#140) montrent l'envers : créer une issue pour chaque reprise donne l'impression de mouvement sans patch ni test. Une seule tâche stable, un journal de tentatives bornées et un blocage explicite sont préférables.

### 19–21 septembre : Studio, Trio, Room et FileBus

L'[encyclopédie historique](https://github.com/VincBZH/bazor-mobile/blob/main/BAZOR_ENCYCLOPEDIA.md) impose préflight sandbox, tests, sauvegarde, rollback et preuves. L'ordre initial était **Core/Watcher → pont Mammouth/Ollama → Room/QUINTO → Studio/H3**. Il reste cohérent pour le logiciel, sous réserve de traiter le démarrage Windows comme précondition pratique.

Studio a prouvé des contrôles de configuration et la présence de ComfyUI, puis un essai utilisateur a révélé que H3 rejetait des noms CLIP/VAE/UNET absents et que l'analyse média échouait avec `Failed to load image or audio file`. La conversion UI → API et la correspondance largeur/hauteur ont entraîné [PR #67](https://github.com/VincBZH/bazor-mobile/pull/67) et plusieurs correctifs. Ce travail était utile : les nœuds réels doivent remplacer les identifiants inventés. En revanche, annoncer « certifié » à partir de 47 contrôles qui ne produisent aucun média utilisable était prématuré.

La coordination GPT (chef/arbitre), Ollama (exécutant local), Mammouth (seconde lecture) a donné un cadre pertinent. Les [PR #80](https://github.com/VincBZH/bazor-mobile/pull/80), [#90](https://github.com/VincBZH/bazor-mobile/pull/90), [#92](https://github.com/VincBZH/bazor-mobile/pull/92), [#94](https://github.com/VincBZH/bazor-mobile/pull/94), [#97](https://github.com/VincBZH/bazor-mobile/pull/97) et [#99](https://github.com/VincBZH/bazor-mobile/pull/99) ont successivement ajouté une revue Trio, priorité locale, chemin rapide, arbitrage, règles sûres et FileBus. Pourquoi les changements successifs ? Les revues externes bloquaient ou dépassaient le délai ; le moteur réellement répondu différait parfois du profil demandé ; des retours « OK » sans texte ni fichier modifié ont été déclassés. La leçon est de montrer **moteur et modèle effectifs, fichier lu, patch, tests, coût et blocage** avant l'enchaînement. FileBus conserve un intérêt sur PC sans téléphone ; la preuve de livraison Studio V4 restait absente malgré la coordination.

Une Room légère a été placée aussi dans `projetWII-ai-relay`. Son README décrit 1 serveur/1 port/1 dossier, AUTO borné et récupération des handoffs invalides : choix précieux. La duplication de source avec `room-payload/` dans `bazor-mobile` rend toutefois la version active ambiguë. Choisir une seule Room installée, conserver ses données, publier sa version et prouver la reprise.

Le tableau/Console Hub dynamique répondait à la demande d'un clic direct, de statuts rafraîchis et d'une console visible. Il a ensuite rencontré des échecs CI de `validate` et des chemins de lancement multiples. Da Bazor doit présenter les fonctions validées sans devenir un troisième orchestrateur caché.

### 24–27 septembre : livrables métier et preuves isolées

**Studio Expert.** Vincent a fixé Pony V6 **SDXL** et AnimateDiff **compatible SDXL**, avec inventaire M0 avant tout chargement lourd ; `mm_sd_v15` et `motion_bucket_id` n'appartiennent pas à ce pipeline. Sur RTX 4060 8 Go / 16 Go RAM, charger simultanément de gros modèles ou ajouter RIFE/upscale avant la fidélité source rend les essais plus lents et plus flous. M3/M3b a produit 8 images et un MP4 ; le rendu reste dégradé. M3c VAE a mesuré PSNR 27,47 et SSIM 0,741 ; le passage à 20 pas était bloqué. M3d n'était pas exécuté. Le projet reste intéressant : interface un clic image→vidéo, métadonnées, galerie, reprise et contrôle visuel. Sortie : image source respectée, MP4 réel jugé acceptable et test sur l'installation 3.0.5. [#161](https://github.com/VincBZH/bazor-mobile/issues/161), [PR #141](https://github.com/VincBZH/bazor-mobile/pull/141).

**Sabrina / Repères.** L'application officielle a été recentrée sur « Comprendre ma situation », « Étudier mes possibilités », « Comparer mes gains » avec trois questions initiales, compléments facultatifs, sauvegarde et exemples non enregistrés. Le défaut métier décisif était la correction du profil qui ne se propageait pas aux simulations déjà créées. Des tests techniques sur la vraie source et un parcours Chrome fictif ont été rapportés, mais l'accès de Sabrina, les huit cas P0 et l'usage Windows/Opera/tactile restent à démontrer. La petite copie locale ou un ZIP documentaire ne remplace pas la source Sites. Le lien WhatsApp peut inspirer des formulations **en privé**, avec dates, accord et validation des faits ; rien de nominatif dans ce dépôt public. [#166](https://github.com/VincBZH/bazor-mobile/issues/166), [état documentaire](https://github.com/VincBZH/bazor-mobile/blob/main/docs/sabrinazor2000/ETAT_2026-09-26_2215.md).

**Pont multi-IA.** [PR #150](https://github.com/VincBZH/bazor-mobile/pull/150) identifie un décalage entre la chaîne de statut HTTP écrite par `curl` et celle recherchée, capable de produire un faux échec Mammouth. Un trajet Ollama→Mammouth→Ollama a renvoyé HTTP 200 mais son marqueur de certification n'était pas conforme. [#171](https://github.com/VincBZH/bazor-mobile/issues/171) rapporte un vrai aller-retour Room→Core→Ollama sur des copies Windows isolées et une restauration simulée. Cela justifie le socle, pas le statut multi-IA permanent livré. NoTrack 401, coût, identité des moteurs, relance après silence et bascule production restent à résoudre. Ollama gratuit d'abord ; Mammouth économique si besoin ; modèle plus puissant pour un problème difficile ; autres fournisseurs seulement avec disponibilité et coût visibles. [#162](https://github.com/VincBZH/bazor-mobile/issues/162).

**Démarrage.** L'audit Windows personnel du 27/09 a trouvé exactement 2 tâches planifiées et 2 éléments de dossier Démarrage liés à BAZOR. La lecture des tâches est partielle ; aucune entrée désactivée et aucun redémarrage vérifié. La transaction ciblée de [PR #175](https://github.com/VincBZH/bazor-mobile/pull/175) a des tests Windows sur copies jetables. Ne pas publier l'inventaire privé et ne pas prétendre que le PC démarre proprement. Da Bazor doit s'ouvrir volontairement, au centre du bureau, et afficher le programme du jour sans lancer un empilement de services.

## 4. Décisions d'abandon, de pause et de conservation

| Objet | Décision au 27/09 | Pourquoi | Ce qui pourrait rester intéressant |
|---|---|---|---|
| **Tous les parcours téléphone** : Command Center/APK, GO depuis mobile, USB/ADB, découverte PC, BLE/watchdog, BAZOR Montre, C28/Da Fit, relais de notifications | **ABANDONNÉS à la demande de Vincent** | Coupures Bluetooth et éloignement ; trop peu fiable quel que soit l'outil ou l'usage. | Retenir le journal, les critères de preuve et les fonctions Core réutilisables sur PC. Ne pas relancer le produit mobile. |
| Router V3–V13, Hub multiples, auto-starts concurrents | Variantes écartées comme point d'entrée principal | Ports, versions et propriétaires d'instance confus. Router V13 a répondu sur 18795 le 26/09, ce n'est pas un échec du code. | Conserver la découverte de contexte et les diagnostics dans une interface unique ; une instance volontaire. |
| TOR ancien combo v1.8.4 | **Suspendu**, pas prouvé inutile | Lanceur ancien fragile/déplacé ; un job V6 et 66 fichiers inspectés, aucun workflow trouvé. | Reprendre seulement si un besoin de transport défini impose Tor après stabilisation Core. |
| Jeu Wii/PC/Switch | **Suspendu** | Effort dispersé pendant les P0 BAZOR. | Reprise après socle ; le dépôt FileBus n'est pas abandonné avec le jeu. |
| MODO Viewer TikTok | **En pause** | Pas de racine locale sûre reliée à Action Engine et aucune livraison contrôlée ici. | Modération/export une fois la chaîne de preuve réutilisable. |
| Festival / BAZOR Audio | **À documenter, hors chaîne P0** | Présence au registre et issue audio #159, mais pas de test d'usage dans cet audit. | Réutiliser la production média Studio après qualité certifiée. |
| BRAIN A.1 | **À intégrer**, pas à lancer en base parallèle | Une mémoire séparée accroît les divergences. | Fusionner mémoire sourcée, SAFE_INDEX, registre et encyclopédie. |
| Mission Locale | **Conservé, documentaire et privé** | Ce n'est pas un module logiciel à pousser dans GitHub. | Retrouver la version finale, vérifier attribution et exports sans publier les pièces. |
| Windows Hello | **Objectif différé** | Le pilote V0 ne possède pas d'autorisation native ; demander un PIN dans une fenêtre serait trompeur. | Jeton natif court lié à une action typée, refus/expiration/STOP testés. |

« Abandonné » qualifie ici **la feuille de route**, pas une suppression physique ni une preuve que le logiciel n'a jamais marché. Le dépôt `bazor-mobile` garde des sources Android historiques ; aucune désinstallation du téléphone n'a été réalisée par cet audit.

## 5. Ce qui aurait dû être fait plus tôt

1. Un registre des **sources canoniques** avec version installée, commit, propriétaire de port et dossier de données ; un seul Room/Core/Studio actif.
2. Un test E2E métier avant de déclarer « livré » : conversation réelle avec modèle identifié, huit cas Sabrina, image et vidéo jugées, export Mission Locale.
3. Le journal des tentatives et critères de sortie avant les boucles d'issues « RETRY », pour arrêter proprement un provider indisponible.
4. Un inventaire M0 et une matrice de compatibilité des modèles réellement installés avant les téléchargements lourds et les patches H3/Pony.
5. La sauvegarde, le test Windows et le rollback production avant de changer les services ou d'ajouter un lancement automatique.
6. Une séparation stricte entre données privées et coordination GitHub : WhatsApp, documents Sabrina, rapports sociaux et commandes de démarrage restent sur PC.
7. Un coût externe explicite et borné ; identité réelle de chaque modèle et décision d'arbitrage visibles.

## 6. Ordre actuel sans téléphone

0. **PC calme.** Relever état de démarrage, désactiver uniquement les quatre entrées reconnues avec sauvegarde réversible, puis observer un redémarrage réel. Couverture partielle à investiguer.
1. **Socle unique.** Vérifier l'instance Core/Room/Ollama installée, puis essai conversationnel et panne/restauration contrôlée sur copies avant production. Da Bazor reste un menu volontaire.
2. **Sabrina.** Reprendre seulement le projet Sites officiel, propager corrections aux simulations, tester les huit cas fictifs, valider accès Sabrina et exporter une V1 simple.
3. **Studio.** Relever M0 et version 3.0.5, corriger H3/Pony compatibles 8 Go, comparer image source/résultat, garder un MP4 acceptable et un rapport E2E.
4. **Mission Locale.** Identifier la version finale privée, relire et exporter PPT/PDF selon la destination.
5. **Multi-IA.** Rebrancher Mammouth avec preuve de modèle et de coût ; supervision avec accusé, délai, retry unique, diagnostic et alternative. NoTrack reste bloqué tant que 401 n'est pas réparé.
6. **Hello et autonomie d'action.** Autorisations Windows natives pour opérations nommées, puis Action Engine et rollback. Les textes IA/GitHub ne deviennent jamais commandes libres.

Le menu Da Bazor visualise cette carte, sonde uniquement `127.0.0.1`, et n'ouvre un outil local qu'après réponse de son endpoint. Il **ne** détecte pas encore l'identité exacte du processus sur un port, ne prouve pas une génération, ne déploie pas les projets et ne modifie pas Windows. Cette limite doit rester visible jusqu'aux preuves de bout en bout.

## 7. Sources à suivre

- [Encyclopédie historique](https://github.com/VincBZH/bazor-mobile/blob/main/BAZOR_ENCYCLOPEDIA.md), [registre](https://github.com/VincBZH/bazor-mobile/blob/main/bazor_registry.json), [tableau #174](https://github.com/VincBZH/bazor-mobile/issues/174), [PR Da Bazor #175](https://github.com/VincBZH/bazor-mobile/pull/175).
- [Architecture #162](https://github.com/VincBZH/bazor-mobile/issues/162), [anti faux PASS #160](https://github.com/VincBZH/bazor-mobile/issues/160), [multi-IA #171](https://github.com/VincBZH/bazor-mobile/issues/171), [Studio #161](https://github.com/VincBZH/bazor-mobile/issues/161), [Sabrina #166](https://github.com/VincBZH/bazor-mobile/issues/166).
- [FileBus #99](https://github.com/VincBZH/bazor-mobile/pull/99), [pont Mammouth #150](https://github.com/VincBZH/bazor-mobile/pull/150), [Room légère](https://github.com/VincBZH/projetWII-ai-relay/blob/main/bazor_room_v2/README.md).

**À compléter sur le PC :** versions installées, chemins exacts validés, rapport privé de démarrage, test après redémarrage, source et exports Mission Locale, preuve d'accès Sabrina, qualité vidéo contrôlée. Aucune conversation WhatsApp n'est disponible dans cet inventaire ; ne pas inventer ses citations.
