"""BAZOR ULTIMATE: diagnostics locaux non destructifs (bibliothèque standard).

La vérification périodique n'utilise que GET sur 127.0.0.1. Un test POST de
conversation locale est disponible UNIQUEMENT sur demande explicite. Aucune
réparation, aucune commande système et aucun fournisseur payant ici.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional

CORE = "http://127.0.0.1:8775/api/v1/health"
ROOM = "http://127.0.0.1:8765/health"
ROOM_LINK = "http://127.0.0.1:8765/api/chat/core"
OLLAMA = "http://127.0.0.1:11434/api/tags"
ROOM_CHAT = "http://127.0.0.1:8765/api/chat"


class State(str, Enum):
    GREEN = "VERT"
    YELLOW = "JAUNE"
    RED = "ROUGE"
    GRAY = "GRIS"


@dataclass(frozen=True)
class Check:
    name: str
    state: State
    detail: str

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class LocalHttp:
    """Transport sans proxy, limité à des URLs loopback déclarées dans ce module."""

    def __init__(self, timeout: float = 2.5):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, url: str, data: Optional[dict[str, Any]] = None) -> tuple[int, Any]:
        if url not in (CORE, ROOM, ROOM_LINK, OLLAMA, ROOM_CHAT):
            raise ValueError("URL de diagnostic non autorisée")
        payload = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="GET" if data is None else "POST",
        )
        with self.opener.open(req, timeout=self.timeout if data is None else 120) as response:
            status = response.status
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError("Réponse trop volumineuse")
        try:
            return int(status), json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return int(status), None


def _read(client: LocalHttp, name: str, url: str) -> tuple[Check, Any]:
    try:
        code, body = client.request(url)
    except urllib.error.HTTPError as exc:
        return Check(name, State.RED, f"HTTP {exc.code}"), None
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return Check(name, State.RED, f"Service injoignable ({type(exc).__name__})"), None
    except Exception as exc:
        return Check(name, State.GRAY, f"Diagnostic impossible ({type(exc).__name__})"), None
    if not 200 <= code < 300:
        return Check(name, State.RED, f"HTTP {code}"), body
    if not isinstance(body, dict):
        return Check(name, State.YELLOW, "Réponse JSON invalide"), body
    if body.get("ok") is False:
        return Check(name, State.RED, "Le service signale ok=false"), body
    return Check(name, State.GREEN, "API accessible"), body


def diagnose(client: Optional[LocalHttp] = None) -> dict[str, Check]:
    """Contrôle GET exclusivement : aucune génération ni action de réparation."""
    client = client or LocalHttp()
    core, core_body = _read(client, "Core", CORE)
    room, room_body = _read(client, "AI Room", ROOM)
    ollama, tags = _read(client, "Ollama", OLLAMA)

    if core.state is State.GREEN:
        if core_body.get("ok") is not True:
            core = Check("Core", State.YELLOW, "Champ de santé ok non confirmé")
        elif isinstance(core_body.get("ollama"), dict) and core_body["ollama"].get("online") is False:
            core = Check("Core", State.YELLOW, "Core actif ; Ollama signalé hors ligne")
    if room.state is State.GREEN and room_body.get("ok") is not True:
        room = Check("AI Room", State.YELLOW, "Champ de santé ok non confirmé")
    if ollama.state is State.GREEN:
        models = tags.get("models")
        if not isinstance(models, list):
            ollama = Check("Ollama", State.YELLOW, "Liste de modèles invalide")
        else:
            names = [m.get("name") or m.get("model") for m in models if isinstance(m, dict)]
            count = sum(isinstance(n, str) and bool(n.strip()) for n in names)
            ollama = (Check("Ollama", State.GREEN, f"{count} modèle(s) disponible(s)") if count
                      else Check("Ollama", State.YELLOW, "Aucun modèle disponible"))

    checks = {"core": core, "room": room, "ollama": ollama}
    if room.state is State.GREEN:
        link, link_body = _read(client, "Liaison Room/Core", ROOM_LINK)
        if link.state is State.GREEN:
            if link_body.get("core") is True and link_body.get("ollama") is True:
                link = Check("Liaison Room/Core", State.GREEN, "Core et Ollama déclarés connectés ; génération non testée")
            elif link_body.get("core") is False or link_body.get("ollama") is False:
                link = Check("Liaison Room/Core", State.YELLOW, "Dépendance signalée indisponible")
            else:
                link = Check("Liaison Room/Core", State.YELLOW, "Statut de liaison incomplet")
        elif link.state is State.RED:
            link = Check("Liaison Room/Core", State.YELLOW, f"Interface active ; {link.detail}")
    else:
        link = Check("Liaison Room/Core", State.GRAY, "Non vérifiée : AI Room indisponible")
    if link.state is State.GREEN and any(
        item.state is not State.GREEN for item in (core, room, ollama)
    ):
        link = Check("Liaison Room/Core", State.YELLOW,
                     "Liaison annoncée prête, mais contrôle indépendant dégradé")
    checks["link"] = link

    states = [core.state, room.state, ollama.state, link.state]
    if State.RED in states:
        overall = State.RED
    elif State.YELLOW in states or (State.GRAY in states and any(s is State.GREEN for s in states)):
        overall = State.YELLOW
    else:
        overall = State.GRAY if State.GRAY in states else State.GREEN
    checks["overall"] = Check("BAZOR local", overall,
                              "Statut API uniquement ; aucun message généré automatiquement")
    return checks


def test_local_chat(client: Optional[LocalHttp] = None) -> Check:
    """APPEL EXPLICITE SEULEMENT : POST AI Room -> Core -> Ollama local."""
    client = client or LocalHttp()
    try:
        code, body = client.request(ROOM_CHAT, {"text": "Réponds uniquement BAZOR_OK"})
    except urllib.error.HTTPError as exc:
        return Check("Conversation locale", State.RED, f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return Check("Conversation locale", State.RED, f"Service injoignable ({type(exc).__name__})")
    except Exception as exc:
        return Check("Conversation locale", State.GRAY, f"Test impossible ({type(exc).__name__})")
    if not 200 <= code < 300:
        return Check("Conversation locale", State.RED, f"HTTP {code}")
    if not isinstance(body, dict):
        return Check("Conversation locale", State.YELLOW, "Réponse JSON invalide")
    if body.get("ok") is not True:
        return Check("Conversation locale", State.RED, "Réponse non confirmée (ok != true)")
    answer = body.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return Check("Conversation locale", State.YELLOW, "Aucun texte de réponse")
    if answer.strip() != "BAZOR_OK":
        return Check("Conversation locale", State.YELLOW, "Réponse reçue, mais différente de BAZOR_OK")
    return Check("Conversation locale", State.GREEN, "Vrai aller-retour local BAZOR_OK confirmé")
