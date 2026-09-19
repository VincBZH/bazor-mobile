PROJECT: BAZOR_TRIO
REQUEST_ID: MAMMOUTH-HELLO-VINCENT-20260919
STATUS_EXPECTED: VERIFIE

TASK:
Réponds exactement en français :
Bonjour Vincent 👋

OBJECTIF:
Test de communication autonome GPT -> GitHub/FileBus -> Mammouth -> watcher -> GitHub.

IMPORTANT:
- Ne pas demander à Vincent de copier-coller.
- Si le client Mammouth permet réellement de faire apparaître un message dans la fenêtre de chat Mammouth déjà ouverte, y publier aussi exactement "Bonjour Vincent 👋".
- Si cette publication dans l'interface Mammouth n'est pas supportée par l'API/runtime, l'indiquer explicitement dans la réponse; ne pas prétendre l'avoir fait.

RESPONSE_FORMAT:
La réponse GitHub doit contenir le texte exact "Bonjour Vincent 👋" et préciser UI_CHAT_POSTED: true|false.

NEXT:
Retourner la preuve via le FileBus.
