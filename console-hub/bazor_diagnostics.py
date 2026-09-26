"""BAZOR ULTIMATE: diagnostic IA local, en lecture seule.

Un HTTP 200 ne prouve ni une conversation ni une liaison entre fournisseurs.
Aucune cle API, aucun POST, aucune commande systeme, aucun appel payant.
"""
import json
import socket
import urllib.error
import urllib.request

CHECKS = (
    ("Core 8775", "http://127.0.0.1:8775/api/v1/health", "core"),
    ("Core 8765 (variante)", "http://127.0.0.1:8765/api/v1/health", "core"),
    ("AI Room 8765", "http://127.0.0.1:8765/api/status", "room"),
    ("Ollama 11434", "http://127.0.0.1:11434/api/tags", "ollama"),
)

def fetch_json(url, timeout=1.4):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "BAZOR-ReadOnly-Diagnostic/1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read(262145)
        if len(data) > 262144:
            raise ValueError("reponse trop volumineuse")
        return response.status, json.loads(data.decode("utf-8"))

def _valid(data, kind):
    if not isinstance(data, dict):
        return False, "JSON inattendu"
    if kind == "core":
        return data.get("ok") is True and data.get("service") == "BAZOR API", "signature Core absente"
    if kind == "room":
        return data.get("ok") is True and isinstance(data.get("engines"), dict), "signature AI Room absente"
    if kind == "ollama":
        models = data.get("models")
        return isinstance(models, list) and len(models) > 0, "aucun modele Ollama confirme"
    return False, "type non pris en charge"

def probe(name, url, kind, fetcher=fetch_json):
    result = {"service": name, "url": url, "etat": "GRIS", "preuve": "aucune"}
    try:
        status, data = fetcher(url)
        if not 200 <= status < 300:
            result.update(etat="ROUGE", preuve="HTTP " + str(status))
            return result, None
        valid, reason = _valid(data, kind)
        if valid:
            detail = "signature JSON validee"
            if kind == "ollama":
                detail += " ; " + str(len(data["models"])) + " modele(s)"
            result.update(etat="VERT", preuve=detail)
        else:
            result.update(etat="JAUNE", preuve="HTTP " + str(status) + " ; " + reason)
        return result, data if valid else None
    except urllib.error.HTTPError as exc:
        color = "JAUNE" if exc.code == 404 else "ROUGE"
        result.update(etat=color, preuve="HTTP " + str(exc.code) + (" ; autre version possible" if exc.code == 404 else ""))
    except (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout):
        result.update(etat="GRIS", preuve="non joignable depuis cet ordinateur")
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        result.update(etat="JAUNE", preuve="reponse JSON invalide")
    except Exception as exc:
        result.update(etat="JAUNE", preuve="erreur de diagnostic : " + type(exc).__name__)
    return result, None

def build_report(fetcher=fetch_json):
    rows = []
    cores = []
    for name, url, kind in CHECKS:
        row, payload = probe(name, url, kind, fetcher=fetcher)
        rows.append(row)
        if kind == "core" and payload is not None:
            cores.append(payload)
    # Etat "configure" n'est JAMAIS une preuve d'un appel API.
    configured = any(isinstance(c.get("mammouth"), dict) and c["mammouth"].get("configured") is True for c in cores)
    rows.append({"service": "Mammouth API", "etat": "JAUNE" if configured else "GRIS",
                 "preuve": "configuration detectee ; appel reel NON teste" if configured else "configuration ou acces non verifies"})
    rows.append({"service": "AI Room -> Core -> Ollama", "etat": "GRIS",
                 "preuve": "conversation de bout en bout NON testee par ce diagnostic GET"})
    rows.append({"service": "Ollama -> Mammouth -> Ollama", "etat": "GRIS",
                 "preuve": "attente du test runtime reel #151, sans secret"})
    rows.append({"service": "GPT / Astra / NoTrack", "etat": "GRIS",
                 "preuve": "aucun appel fournisseur dans ce diagnostic"})
    return rows

def render_text(rows):
    return "\n".join("[" + r["etat"] + "] " + r["service"] + " : " + r["preuve"] for r in rows)

if __name__ == "__main__":
    import sys
    rows = build_report()
    if "--json" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(render_text(rows))
