import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

TEXT_EXTS = {
    ".txt",".md",".markdown",".json",".jsonl",".csv",".tsv",
    ".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".html",".htm",".css",
    ".java",".kt",".kts",".c",".h",".cpp",".hpp",".cs",".go",".rs",
    ".php",".rb",".sh",".bat",".cmd",".ps1",".yml",".yaml",".xml",
    ".ini",".cfg",".conf",".sql",".toml",".gradle",".properties"
}
SKIP_PARTS = {
    ".git","node_modules","models","checkpoints","output","outputs",
    "venv",".venv","__pycache__","cache","temp","tmp","downloads",
    "bazor_data","hub_logs","action_backups","action_reports"
}
MAX_CONTEXT_SCAN_FILES = 5000
MAX_CONTEXT_SCAN_SECONDS = 3.0
DENY_NAMES = {
    ".env","security_state.json","credentials.json","secrets.json",
    "id_rsa","id_ed25519","known_hosts"
}
MAX_FILE_BYTES = 800_000
MAX_CREATE_BYTES = 350_000
MAX_ACTIONS = 8

class ActionEngine:
    """
    BAZOR controlled file action engine.

    No arbitrary shell commands are accepted from the model/mobile.
    Supported operations are text-only: replace and create.
    Every change is backed up, validated and rolled back on deterministic test failure.
    """

    def __init__(self, data_dir, journal_cb=None):
        self.data_dir = Path(data_dir)
        self.backup_root = self.data_dir / "ACTION_BACKUPS"
        self.report_root = self.data_dir / "ACTION_REPORTS"
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.report_root.mkdir(parents=True, exist_ok=True)
        self.journal_cb = journal_cb
        home = Path.home()
        localapp = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
        self.roots = {
            "bazor_repo": home / "bazor-mobile",
            "ai_room": localapp / "BazorAIROOM",
            "simple_studio": Path(r"C:\AI\SimpleStudioV2"),
            "wii": Path(r"C:\projetWII"),
            "bazor_tools": Path(r"C:\BAZOR TOOL"),
        }
        self.project_aliases = {
            "ai-room": ["bazor_repo", "ai_room"],
            "bazor-security": ["bazor_repo"],
            "bazor-tools": ["bazor_repo", "bazor_tools"],
            "simple-studio": ["simple_studio"],
            "wii": ["wii"],
            "wii-relay": ["wii"],
        }

    def _journal(self, event, details):
        if not self.journal_cb:
            return
        try:
            self.journal_cb(event, details)
        except Exception:
            pass

    def available_roots(self, project_id):
        out = []
        for alias in self.project_aliases.get(str(project_id or ""), []):
            root = self.roots.get(alias)
            if root and root.exists():
                out.append({"alias": alias, "path": str(root)})
        return out

    def _allowed_aliases(self, project_id):
        return set(self.project_aliases.get(str(project_id or ""), []))

    def _safe_path(self, project_id, alias, relpath, must_exist=None):
        alias = str(alias or "").strip()
        if alias not in self._allowed_aliases(project_id):
            raise ValueError("root_alias_not_allowed")
        root = self.roots.get(alias)
        if not root or not root.exists():
            raise ValueError("root_unavailable")
        raw = str(relpath or "").replace("\\","/").strip().lstrip("/")
        if not raw or raw.startswith("../") or "/../" in ("/"+raw):
            raise ValueError("invalid_relative_path")
        rel = Path(raw)
        if rel.is_absolute():
            raise ValueError("absolute_path_forbidden")
        if any(part.lower() in SKIP_PARTS for part in rel.parts):
            raise ValueError("path_in_skipped_area")
        if rel.name.lower() in DENY_NAMES:
            raise ValueError("sensitive_file_forbidden")
        if any(x in rel.name.lower() for x in ("password","passwd","credential","private_key","secret_key","api_key")):
            raise ValueError("sensitive_name_forbidden")
        if rel.suffix.lower() not in TEXT_EXTS:
            raise ValueError("extension_not_allowed")
        target = (root / rel).resolve()
        root_resolved = root.resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            raise ValueError("path_escape_forbidden")
        if must_exist is True and not target.is_file():
            raise ValueError("target_missing")
        if must_exist is False and target.exists():
            raise ValueError("target_already_exists")
        return root, target, raw

    def context_for_project(self, project_id, max_files=24, max_chars=76000):
        aliases = self.available_roots(project_id)
        candidates = []
        started = time.monotonic()
        deadline = started + MAX_CONTEXT_SCAN_SECONDS
        scanned_files = 0
        scan_limited = False

        # GO tourne dans un thread du Core. Un Path.rglob("*") descendait malgré
        # les dossiers à ignorer (.git, models, logs, etc.) puis les rejetait
        # seulement après coup. Sur les gros projets cela pouvait monopoliser
        # disque/CPU assez longtemps pour faire expirer les requêtes du mobile.
        # os.walk permet de couper ces branches AVANT de les parcourir.
        for info in aliases:
            alias = info["alias"]
            root = Path(info["path"])
            try:
                for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
                    dirs[:] = [d for d in dirs if d.lower() not in SKIP_PARTS]
                    if time.monotonic() >= deadline or scanned_files >= MAX_CONTEXT_SCAN_FILES:
                        scan_limited = True
                        break

                    current_path = Path(current)
                    for name in names:
                        scanned_files += 1
                        if scanned_files % 250 == 0:
                            time.sleep(0)  # rend la main aux threads HTTP du Core
                        if time.monotonic() >= deadline or scanned_files > MAX_CONTEXT_SCAN_FILES:
                            scan_limited = True
                            break

                        p = current_path / name
                        if p.suffix.lower() not in TEXT_EXTS:
                            continue
                        try:
                            rel = p.relative_to(root)
                        except Exception:
                            continue
                        if any(part.lower() in SKIP_PARTS for part in rel.parts):
                            continue
                        if rel.name.lower() in DENY_NAMES:
                            continue
                        try:
                            st = p.stat()
                        except Exception:
                            continue
                        if st.st_size > 512000:
                            continue
                        candidates.append((st.st_mtime, alias, root, p))

                    if scan_limited:
                        break
            except Exception:
                continue
            if scan_limited:
                break

        candidates.sort(reverse=True)
        chunks, files, used = [], [], 0
        for _, alias, root, p in candidates:
            if len(files) >= max_files or used >= max_chars:
                break
            try:
                raw = p.read_bytes()
                text = None
                for enc in ("utf-8","utf-8-sig","cp1252","latin-1"):
                    try:
                        text = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                if text is None:
                    continue
                rel = str(p.relative_to(root)).replace("\\","/")
                remain = max_chars - used
                if remain <= 1000:
                    break
                body = text[:min(14000, remain)]
                chunks.append(f"\n--- ROOT:{alias} FILE:{rel} ---\n{body}")
                files.append({"root":alias,"path":rel,"size":len(raw)})
                used += len(body)
            except Exception:
                continue

        scan_ms = int((time.monotonic() - started) * 1000)
        return "".join(chunks), {
            "available": bool(files),
            "roots": aliases,
            "files": files,
            "chars": used,
            "scan_ms": scan_ms,
            "scanned_files": scanned_files,
            "scan_limited": scan_limited,
        }

    def parse_actions(self, answer):
        text = str(answer or "")
        marker = re.search(r"(?i)BAZOR_ACTIONS\s*:", text)
        if not marker:
            return []
        rest = text[marker.end():].lstrip()
        if rest.startswith("```"):
            nl = rest.find("\n")
            if nl >= 0:
                rest = rest[nl+1:]
            end = rest.find("```")
            if end >= 0:
                rest = rest[:end]
        rest = rest.lstrip()
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(rest)
        except Exception:
            return []
        actions = obj.get("actions") if isinstance(obj, dict) else None
        if not isinstance(actions, list):
            return []
        return actions[:MAX_ACTIONS]

    def _hash_bytes(self, data):
        return hashlib.sha256(data).hexdigest()

    def _validate_action(self, project_id, action):
        if not isinstance(action, dict):
            raise ValueError("action_not_object")
        op = str(action.get("op") or "").strip().lower()
        alias = str(action.get("root") or "").strip()
        rel = str(action.get("path") or "").strip()
        if op == "replace":
            root, target, raw = self._safe_path(project_id, alias, rel, must_exist=True)
            data = target.read_bytes()
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("target_too_large")
            try:
                text = data.decode("utf-8")
                enc = "utf-8"
            except UnicodeDecodeError:
                try:
                    text = data.decode("utf-8-sig")
                    enc = "utf-8-sig"
                except UnicodeDecodeError:
                    raise ValueError("target_not_utf8")
            find = str(action.get("find") or "")
            repl = str(action.get("replace") or "")
            if not find:
                raise ValueError("find_missing")
            count = text.count(find)
            expected = int(action.get("expected_count", 1) or 1)
            if expected < 1 or expected > 20:
                raise ValueError("expected_count_invalid")
            if count != expected:
                raise ValueError(f"find_count_mismatch:{count}!={expected}")
            new_text = text.replace(find, repl, expected)
            if new_text == text:
                raise ValueError("no_change")
            return {
                "op": op, "root": alias, "path": raw, "target": target,
                "before": data, "after": new_text.encode(enc),
                "encoding": enc, "expected_count": expected
            }
        if op == "create":
            root, target, raw = self._safe_path(project_id, alias, rel, must_exist=False)
            content = str(action.get("content") or "")
            data = content.encode("utf-8")
            if not data or len(data) > MAX_CREATE_BYTES:
                raise ValueError("create_size_invalid")
            return {
                "op": op, "root": alias, "path": raw, "target": target,
                "before": None, "after": data, "encoding": "utf-8"
            }
        raise ValueError("operation_not_allowed")

    def _run_test_for_file(self, path):
        ext = path.suffix.lower()
        try:
            raw = path.read_bytes()
        except Exception as exc:
            return {"file":str(path),"ok":False,"test":"read","detail":str(exc)[:180]}
        if ext == ".py":
            try:
                src = raw.decode("utf-8")
                compile(src, str(path), "exec")
                return {"file":str(path),"ok":True,"test":"python_compile"}
            except Exception as exc:
                return {"file":str(path),"ok":False,"test":"python_compile","detail":f"{type(exc).__name__}: {exc}"[:240]}
        if ext in (".json",".jsonl"):
            try:
                text = raw.decode("utf-8-sig")
                if ext == ".json":
                    json.loads(text)
                else:
                    for line in text.splitlines():
                        if line.strip():
                            json.loads(line)
                return {"file":str(path),"ok":True,"test":"json_parse"}
            except Exception as exc:
                return {"file":str(path),"ok":False,"test":"json_parse","detail":f"{type(exc).__name__}: {exc}"[:240]}
        if ext in (".js",".mjs",".cjs"):
            node = shutil.which("node")
            if node:
                try:
                    p=subprocess.run([node,"--check",str(path)],capture_output=True,text=True,timeout=12,creationflags=CREATE_NO_WINDOW)
                    return {"file":str(path),"ok":p.returncode==0,"test":"node_check","detail":(p.stderr or p.stdout).strip()[:240]}
                except Exception as exc:
                    return {"file":str(path),"ok":False,"test":"node_check","detail":str(exc)[:240]}
        if ext == ".ps1" and os.name == "nt":
            try:
                script = "$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$t,[ref]$e)|Out-Null;if($e.Count){$e|%{$_.Message};exit 1}"
                p=subprocess.run(["powershell","-NoProfile","-Command",script,str(path)],capture_output=True,text=True,timeout=12,creationflags=CREATE_NO_WINDOW)
                return {"file":str(path),"ok":p.returncode==0,"test":"powershell_parse","detail":(p.stderr or p.stdout).strip()[:240]}
            except Exception as exc:
                return {"file":str(path),"ok":False,"test":"powershell_parse","detail":str(exc)[:240]}
        return {"file":str(path),"ok":True,"test":"text_write_verified"}

    def apply(self, project_id, actions, request_id=None):
        request_id = re.sub(r"[^A-Za-z0-9._-]+","_",str(request_id or ""))[:80] or time.strftime("%Y%m%d_%H%M%S")
        result = {
            "ok": False, "applied": False, "rolled_back": False,
            "request_id": request_id, "actions": [], "tests": [], "files": [],
        }
        if not actions:
            result.update({"ok":True,"reason":"no_actions"})
            return result
        prepared=[]
        try:
            seen_targets=set()
            for a in actions[:MAX_ACTIONS]:
                item=self._validate_action(project_id, a)
                key=str(item["target"]).lower()
                if key in seen_targets:
                    raise ValueError("duplicate_target_in_action_set")
                seen_targets.add(key)
                prepared.append(item)
        except Exception as exc:
            result["error"]="validation_failed"
            result["detail"]=str(exc)[:240]
            self._journal("ACTION_ENGINE_REJECTED", {"project":project_id,"request_id":request_id,"detail":result["detail"]})
            return result

        backup_dir = self.backup_root / request_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        written=[]
        try:
            for i,item in enumerate(prepared):
                target=item["target"]
                target.parent.mkdir(parents=True, exist_ok=True)
                before=item["before"]
                if before is not None:
                    backup = backup_dir / f"{i:02d}_{item['root']}_{Path(item['path']).name}.bak"
                    backup.write_bytes(before)
                target.write_bytes(item["after"])
                written.append(item)
                result["actions"].append({"op":item["op"],"root":item["root"],"path":item["path"]})
                result["files"].append({
                    "root":item["root"],"path":item["path"],
                    "before_sha256": self._hash_bytes(before) if before is not None else None,
                    "after_sha256": self._hash_bytes(item["after"]),
                })

            tests=[]
            seen=set()
            for item in written:
                key=str(item["target"])
                if key in seen:
                    continue
                seen.add(key)
                tests.append(self._run_test_for_file(item["target"]))
            result["tests"]=tests
            if not all(t.get("ok") for t in tests):
                raise RuntimeError("deterministic_test_failed")
            result["ok"]=True
            result["applied"]=True
            result["backup_dir"]=str(backup_dir)
            self._journal("ACTION_ENGINE_APPLIED", {
                "project":project_id,"request_id":request_id,
                "files":[f"{x['root']}:{x['path']}" for x in result["files"]],
                "tests":tests,
            })
        except Exception as exc:
            for item in reversed(written):
                try:
                    if item["before"] is None:
                        if item["target"].exists():
                            item["target"].unlink()
                    else:
                        item["target"].write_bytes(item["before"])
                except Exception:
                    pass
            result["rolled_back"]=True
            result["error"]="apply_or_test_failed"
            result["detail"]=str(exc)[:240]
            self._journal("ACTION_ENGINE_ROLLBACK", {
                "project":project_id,"request_id":request_id,"detail":result["detail"]
            })
        try:
            report=self.report_root / f"{request_id}.json"
            report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
            result["report_file"]=str(report)
        except Exception:
            pass
        return result
