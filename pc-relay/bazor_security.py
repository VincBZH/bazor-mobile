import base64
import ctypes
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

class BazorSecurity:
    def __init__(self, data_dir, journal_cb=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "security_state.json"
        self.alert_file = self.data_dir / "security_alerts.jsonl"
        self.journal_cb = journal_cb
        self.lock = threading.RLock()
        self.challenges = {}
        self._pair_code = None
        self._pair_expires = 0
        self._pair_hash = None
        self._last_pair_display = 0
        self._last_pair_success = 0
        self.state = self._load()
        pairing = self.state.get("pairing") or {}
        if float(pairing.get("expires", 0) or 0) > time.time() and pairing.get("hash"):
            self._pair_hash = str(pairing.get("hash"))
            self._pair_expires = float(pairing.get("expires"))
        # Premier appairage seulement : on crée un code si aucun code encore valide n'existe.
        if not bool(self.state.get("devices")) and not self._pair_hash:
            self.rotate_pair_code(force=True)

    def _load(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("devices", {})
                    data.setdefault("approvals", [])
                    data.setdefault("pairing", {})
                    data.setdefault("settings", {"require_auth": True, "allow_private_vpn": True})
                    return data
            except Exception:
                pass
        return {"version": 1, "devices": {}, "approvals": [], "pairing": {}, "settings": {"require_auth": True, "allow_private_vpn": True}}

    def _save(self):
        self.state_file.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(self.state_file, 0o600)
        except Exception:
            pass

    def _event(self, event, details):
        row = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **(details or {})}
        try:
            with self.alert_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass
        try:
            if self.journal_cb:
                self.journal_cb(event, details or {})
        except Exception:
            pass

    def alert(self, reason, ip=None, device_id=None, extra=None):
        self._event("SECURITY_ALERT", {"reason": reason, "ip": ip, "device_id": device_id, "extra": extra or {}})

    def _pair_digest(self, code):
        return hashlib.sha256(str(code or "").strip().upper().encode("utf-8")).hexdigest()

    def rotate_pair_code(self, force=False):
        with self.lock:
            now = time.time()
            active = bool(self._pair_hash and now < self._pair_expires)
            if force or not active:
                alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
                raw = "".join(secrets.choice(alphabet) for _ in range(12))
                self._pair_code = "-".join(raw[i:i+4] for i in range(0, 12, 4))
                self._pair_hash = self._pair_digest(self._pair_code)
                self._pair_expires = now + 600
                self.state["pairing"] = {"hash": self._pair_hash, "expires": self._pair_expires, "created": now}
                self._save()
            return self._pair_code

    def pairing_console_text(self):
        now = time.time()
        if self._pair_hash and now < self._pair_expires and not self._pair_code:
            mins = max(0, int((self._pair_expires - now) / 60))
            return (
                "\n" + "=" * 68 + "\n"
                + "  BAZOR SECURITY - APPAIRAGE EN COURS\n"
                + "  Le code precedent reste VALIDE apres redemarrage du Core.\n"
                + f"  Encore environ {mins} minute(s).\n"
                + "  Pour un nouveau code: demande-le depuis BAZOR Mobile/Console Hub.\n"
                + "=" * 68
            )
        if not self._pair_hash or now >= self._pair_expires:
            if self.state.get("devices"):
                return "[SECURITY] Telephone deja appaire - aucun code d'appairage actif."
            self.rotate_pair_code(force=True)
        mins = max(0, int((self._pair_expires - time.time()) / 60))
        return (
            "\n"
            + "=" * 68 + "\n"
            + "  BAZOR SECURITY - CODE D'APPAIRAGE MOBILE\n"
            + "  >>> " + str(self._pair_code) + " <<<\n"
            + f"  Valable environ {mins} minute(s) - ne pas partager\n"
            + "  Le code reste valide meme si le Core redemarre.\n"
            + "=" * 68
        )

    def print_pairing_console(self):
        text = self.pairing_console_text()
        if os.name == "nt":
            try:
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                # Fond jaune vif + texte noir pour rendre le code tres visible.
                kernel32.SetConsoleTextAttribute(handle, 0xE0)
                print(text, flush=True)
                kernel32.SetConsoleTextAttribute(handle, 0x07)
                return
            except Exception:
                pass
        # Repli ANSI: jaune vif.
        print("\033[93m" + text + "\033[0m", flush=True)

    def request_pairing_display(self, ip=None):
        """Rotate/print a fresh code on the PC only. Never return the code to the requester."""
        with self.lock:
            now = time.time()
            # Avoid LAN spam constantly invalidating a code the owner is typing.
            if now - self._last_pair_display < 20:
                return {"ok": True, "printed": False, "retry_in": int(20 - (now - self._last_pair_display))}
            self._last_pair_display = now
            self.rotate_pair_code(force=True)
            self.print_pairing_console()
            self._event("PAIRING_CODE_DISPLAYED", {"ip": ip})
            return {"ok": True, "printed": True, "expires_in": max(0, int(self._pair_expires - now))}

    def local_pairing_code(self, rotate=False):
        """PC-local helper for the Hub. Raw code is returned only on loopback.
        A new code is generated only when explicitly requested."""
        with self.lock:
            now = time.time()
            if rotate:
                self.rotate_pair_code(force=True)
                self._last_pair_display = now
                self._event("PAIRING_CODE_LOCAL_PC", {"rotate": True})
            active_raw = bool(self._pair_code and self._pair_hash and time.time() < self._pair_expires)
            return {
                "ok": True,
                "code": self._pair_code if active_raw else None,
                "expires_in": max(0, int(self._pair_expires - time.time())),
                "pairing_active": bool(self._pair_hash and time.time() < self._pair_expires),
                "raw_code_available": active_raw,
            }

    def public_status(self):
        with self.lock:
            return {
                "ok": True,
                "paired_devices": len(self.state.get("devices", {})),
                "pairing_required": len(self.state.get("devices", {})) == 0,
                "pairing_available": True,
                "pairing_expires_in": max(0, int(self._pair_expires - time.time())),
                "pairing_active": bool(self._pair_hash and time.time() < self._pair_expires),
                "pairing_guard_seconds": max(0, int(20 - (time.time() - self._last_pair_success))) if self._last_pair_success else 0,
                "mode": "device-proof",
                "biometric": {"mode": "webauthn_or_android_keystore", "server_stores_fingerprint": False},
                "vpn_tolerant": bool(self.state.get("settings", {}).get("allow_private_vpn", True)),
                "require_auth": bool(self.state.get("settings", {}).get("require_auth", True)),
            }

    def pair(self, code, device_id, device_name, ip):
        code = str(code or "").strip().upper()
        device_id = str(device_id or "").strip()[:120]
        device_name = str(device_name or "Mobile BAZOR").strip()[:120]
        with self.lock:
            if not device_id:
                return {"ok": False, "error": "device_id_missing"}
            candidate_hash = self._pair_digest(code)
            if time.time() >= self._pair_expires or not self._pair_hash or not secrets.compare_digest(candidate_hash, self._pair_hash):
                self.alert("pairing_code_invalid", ip, device_id)
                return {"ok": False, "error": "pairing_code_invalid"}
            secret = secrets.token_urlsafe(32)
            self.state["devices"][device_id] = {
                "name": device_name,
                "secret": secret,
                "created_at": time.time(),
                "last_seen": time.time(),
                "last_ip": ip,
                "trusted": True,
                "revoked": False,
            }
            self._save()
            self._event("DEVICE_PAIRED", {"device_id": device_id, "name": device_name, "ip": ip})
            # Le code vient d'être consommé : on l'invalide sans en créer un nouveau.
            self._pair_code = None
            self._pair_hash = None
            self._pair_expires = 0
            self.state["pairing"] = {}
            self._last_pair_success = time.time()
            self._save()
            return {"ok": True, "device_id": device_id, "secret": secret, "name": device_name}

    def challenge(self, device_id, ip):
        with self.lock:
            dev = self.state.get("devices", {}).get(str(device_id or ""))
            if not dev or dev.get("revoked"):
                self.alert("challenge_unknown_device", ip, device_id)
                return {"ok": False, "error": "unknown_device"}
            nonce = secrets.token_urlsafe(24)
            self.challenges[nonce] = {"device_id": device_id, "expires": time.time() + 60, "ip": ip}
            if len(self.challenges) > 200:
                cutoff = time.time()
                self.challenges = {k:v for k,v in self.challenges.items() if v.get("expires",0) > cutoff}
            return {"ok": True, "nonce": nonce, "expires_in": 60}

    def verify(self, device_id, nonce, proof, ip):
        with self.lock:
            dev = self.state.get("devices", {}).get(str(device_id or ""))
            ch = self.challenges.pop(str(nonce or ""), None)
            if not dev or dev.get("revoked"):
                self.alert("auth_unknown_device", ip, device_id)
                return False, "unknown_device"
            if not ch or ch.get("device_id") != device_id or ch.get("expires", 0) < time.time():
                self.alert("auth_bad_or_expired_challenge", ip, device_id)
                return False, "bad_challenge"
            expected = hashlib.sha256((str(nonce) + "|" + str(device_id) + "|" + dev.get("secret","")).encode("utf-8")).hexdigest()
            if not secrets.compare_digest(expected, str(proof or "").lower()):
                self.alert("auth_bad_proof", ip, device_id)
                return False, "bad_proof"
            old_ip = dev.get("last_ip")
            dev["last_seen"] = time.time()
            dev["last_ip"] = ip
            if old_ip and old_ip != ip:
                self._event("DEVICE_IP_CHANGED", {"device_id": device_id, "old_ip": old_ip, "new_ip": ip, "note": "VPN ou changement Wi-Fi possible"})
            self._save()
            return True, "ok"

    def device_summary(self, device_id):
        with self.lock:
            d = self.state.get("devices", {}).get(str(device_id or ""))
            if not d:
                return None
            return {k:v for k,v in d.items() if k != "secret"}

    def alerts(self, limit=40):
        if not self.alert_file.exists():
            return []
        try:
            lines = self.alert_file.read_text(encoding="utf-8").splitlines()[-max(1,min(int(limit),100)):]
            return [json.loads(x) for x in lines if x.strip()][::-1]
        except Exception:
            return []

    def pending_approvals(self):
        now = time.time()
        with self.lock:
            self.state["approvals"] = [a for a in self.state.get("approvals", []) if a.get("expires", now+1) > now and a.get("status") == "PENDING"]
            return list(self.state["approvals"])

    def request_approval(self, action, details=None, ttl=300):
        with self.lock:
            item = {
                "id": secrets.token_urlsafe(12),
                "action": str(action)[:160],
                "details": details or {},
                "created": time.time(),
                "expires": time.time()+max(30,min(int(ttl),3600)),
                "status": "PENDING",
            }
            self.state.setdefault("approvals", []).append(item)
            self._save()
            self._event("APPROVAL_REQUESTED", {"id": item["id"], "action": item["action"]})
            return item

    def decide_approval(self, approval_id, decision, device_id):
        with self.lock:
            for a in self.state.get("approvals", []):
                if a.get("id") == approval_id and a.get("status") == "PENDING":
                    a["status"] = "APPROVED" if str(decision).upper() == "APPROVE" else "DENIED"
                    a["decided_by"] = device_id
                    a["decided_at"] = time.time()
                    self._save()
                    self._event("APPROVAL_DECIDED", {"id": approval_id, "status": a["status"], "device_id": device_id})
                    return {"ok": True, "approval": a}
            return {"ok": False, "error": "approval_not_found"}
