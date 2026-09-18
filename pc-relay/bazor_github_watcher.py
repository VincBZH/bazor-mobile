import json, subprocess, time, urllib.request, os, sys

REPO="VincBZH/bazor-mobile"
CORE="http://127.0.0.1:8775/api/v1/chat"
CORE_HEALTH="http://127.0.0.1:8775/api/v1/security/status"
CORE_FAILS=0
PENDING_CORE_RESTART=False
POLL=10
MARK="[BAZOR-WATCHER-DONE]"
DIAG_MARK="[BAZOR-DIAG-DONE]"
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
PENDING_RESTART_FILE=os.path.join(ROOT,"pc-relay","BAZOR_DATA","pending_core_restart.flag")
LAST_HEAD=None
HUB_LOG_DIR=os.path.join(ROOT,"pc-relay","BAZOR_DATA","HUB_LOGS")
CORE_LOG=os.path.join(HUB_LOG_DIR,"core.log")
WATCHER_LOCK_PORT=8791
_WATCHER_LOCK=None

def _single_instance():
    global _WATCHER_LOCK
    try:
        import socket
        s=socket.socket()
        s.bind(("127.0.0.1",WATCHER_LOCK_PORT))
        s.listen(1)
        _WATCHER_LOCK=s
        return True
    except OSError:
        return False


def _git(*args):
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    return subprocess.run(["git","-C",ROOT,*args],capture_output=True,text=True,encoding="utf-8",errors="replace",creationflags=flags)

def _restart_core():
    core_script=os.path.join(ROOT,"pc-relay","bazor_pc_relay_v3.py")
    try:
        os.makedirs(HUB_LOG_DIR,exist_ok=True)
        if os.name=="nt":
            ps=r"""Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'bazor_pc_relay_v3\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"""
            subprocess.run(["powershell","-NoProfile","-Command",ps],capture_output=True,text=True,timeout=12,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            flags=getattr(subprocess,"CREATE_NO_WINDOW",0) | getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
        else:
            flags=0
        env=os.environ.copy()
        env["BAZOR_MOBILE_PORT"]="8775"
        log=open(CORE_LOG,"a",encoding="utf-8",buffering=1)
        subprocess.Popen([sys.executable,core_script],cwd=os.path.dirname(core_script),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        print("[OK CORE RESTART] BAZOR Core 8775 relance en arriere-plan; log centralise dans le Hub.")
    except Exception as e:
        print("[BLOQUE CORE RESTART]",type(e).__name__,str(e))

def _security_restart_guard():
    try:
        with urllib.request.urlopen(CORE_HEALTH,timeout=2.0) as r:
            data=json.loads(r.read().decode("utf-8"))
        return int(data.get("pairing_expires_in",0) or 0), int(data.get("pairing_guard_seconds",0) or 0)
    except Exception:
        return 0,0

def maybe_restart_core(reason="update"):
    global PENDING_CORE_RESTART
    pairing,guard=_security_restart_guard()
    if pairing>0 or guard>0:
        PENDING_CORE_RESTART=True
        try:
            os.makedirs(os.path.dirname(PENDING_RESTART_FILE),exist_ok=True)
            open(PENDING_RESTART_FILE,"w",encoding="utf-8").write(reason)
        except Exception:
            pass
        print(f"[CORE RESTART DIFFERE] {reason} - appairage actif/protege ({max(pairing,guard)} s).")
        return False
    PENDING_CORE_RESTART=False
    try:
        if os.path.exists(PENDING_RESTART_FILE):
            os.remove(PENDING_RESTART_FILE)
    except Exception:
        pass
    _restart_core()
    return True

def ensure_core_alive():
    global CORE_FAILS,PENDING_CORE_RESTART
    try:
        with urllib.request.urlopen(CORE_HEALTH,timeout=2.0) as r:
            if 200 <= r.status < 300:
                if CORE_FAILS:
                    print("[OK CORE] BAZOR Core 8775 repond de nouveau.")
                CORE_FAILS=0
                if PENDING_CORE_RESTART or os.path.exists(PENDING_RESTART_FILE):
                    maybe_restart_core("mise a jour differee")
                return True
    except Exception:
        pass
    CORE_FAILS += 1
    print(f"[CORE CHECK] Core 8775 ne repond pas ({CORE_FAILS}/3)")
    if CORE_FAILS >= 3:
        print("[CORE RECOVERY] Relance automatique du Core...")
        maybe_restart_core("health")
        CORE_FAILS=0
    elif PENDING_CORE_RESTART:
        maybe_restart_core("mise a jour differee")
    return False

def _run_hub_expert_review():
    script=os.path.join(ROOT,"console-hub","bazor_hub_expert_review.py")
    log_path=os.path.join(ROOT,"pc-relay","BAZOR_DATA","HUB_LOGS","expert_review_runner.log")
    if not os.path.exists(script):
        return
    try:
        os.makedirs(os.path.dirname(log_path),exist_ok=True)
        log=open(log_path,"a",encoding="utf-8",buffering=1)
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        subprocess.Popen([sys.executable,script],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        print("[HUB REVIEW] Tests + revue Mammouth lances en arriere-plan.")
    except Exception as e:
        print("[BLOQUE HUB REVIEW]",type(e).__name__,str(e))

def safe_update():
    global LAST_HEAD
    try:
        p=_git("fetch","origin","main")
        if p.returncode:
            print("[BLOQUE UPDATE] git fetch :", (p.stderr or p.stdout).strip())
            return
        local=_git("rev-parse","HEAD").stdout.strip()
        remote=_git("rev-parse","origin/main").stdout.strip()
        if remote and remote != local:
            changed=_git("diff","--name-only",local,remote).stdout.splitlines()
            print("[UPDATE] Nouvelle version BAZOR detectee :",remote[:7])
            p=_git("merge","--ff-only","origin/main")
            if p.returncode:
                print("[BLOQUE UPDATE]",(p.stderr or p.stdout).strip())
                return
            print("[OK UPDATE] BAZOR mis a jour :",remote[:7])
            LAST_HEAD=remote

            # Actions locales PREDEFINIES uniquement : aucun ordre shell ne vient de GitHub.
            if any(x in changed for x in ("pc-relay/bazor_pc_relay_v3.py","pc-relay/mammouth_client.py","pc-relay/bazor_security.py","pc-relay/bazor_action_engine.py")):
                maybe_restart_core("mise a jour de code")

            if any(
                x.startswith("console-hub/") or x in ("LANCER_BAZOR_CONSOLE_HUB.cmd","LANCER_BAZOR_MOBILE_TOUT_EN_UN.cmd")
                for x in changed
            ):
                _run_hub_expert_review()

            if "pc-relay/bazor_github_watcher.py" in changed:
                print("[SELF UPDATE] Rechargement du watcher avec la nouvelle version...")
                os.execv(sys.executable,[sys.executable,os.path.abspath(__file__)])
        else:
            LAST_HEAD=local
    except Exception as e:
        print("[BLOQUE UPDATE]",type(e).__name__,str(e))

def _read_json(path):
    try:
        with open(path,"r",encoding="utf-8-sig",errors="replace") as f:
            data=json.load(f)
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}

def _tail_text(path,max_lines=400):
    try:
        with open(path,"r",encoding="utf-8",errors="replace") as f:
            lines=f.read().splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""

def _url_ok(url,timeout=2.0):
    try:
        with urllib.request.urlopen(url,timeout=timeout) as r:
            return 200 <= getattr(r,"status",200) < 500
    except Exception:
        return False

def _force_usb_localhost(open_phone=True):
    script=os.path.join(ROOT,"console-hub","bazor_usb_android_bridge.ps1")
    if os.name!="nt" or not os.path.exists(script):
        return {"ok":False,"reason":"usb_bridge_unavailable"}
    args=["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",script,"-Root",ROOT]
    if open_phone:
        args.append("-OpenPhone")
    try:
        p=subprocess.run(
            args,capture_output=True,text=True,encoding="utf-8",errors="replace",
            timeout=55,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        )
    except Exception as e:
        return {"ok":False,"reason":type(e).__name__}
    status=_read_json(os.path.join(ROOT,"pc-relay","BAZOR_DATA","usb_android_status.json"))
    return {
        "ok":bool(status.get("ok")),
        "connected":bool(status.get("connected")),
        "core_reverse":bool(status.get("core_reverse")),
        "web_reverse":bool(status.get("web_reverse")),
        "reason":status.get("reason"),
        "returncode":p.returncode,
    }

def _latest_task_diag():
    path=os.path.join(ROOT,"pc-relay","BAZOR_DATA","journal.jsonl")
    try:
        with open(path,"r",encoding="utf-8",errors="replace") as f:
            lines=f.read().splitlines()[-1200:]
    except Exception:
        return {}
    rows=[]
    for line in lines:
        try:
            row=json.loads(line)
            if row.get("event") in (
                "MOBILE_TASK_JOB_START","MOBILE_TASK_CONTEXT","MOBILE_TASK_JOB_DONE",
                "MOBILE_SUBTASK","SECURITY_ALERT"
            ):
                rows.append(row)
        except Exception:
            pass
    if not rows:
        return {}
    starts=[x for x in rows if x.get("event")=="MOBILE_TASK_JOB_START"]
    if not starts:
        return {"events_seen":len(rows)}
    start=starts[-1]
    rid=start.get("request_id")
    relevant=[x for x in rows if x.get("request_id")==rid or (
        x.get("event")=="MOBILE_TASK_CONTEXT"
        and x.get("project")==start.get("project")
        and x.get("subproject")==start.get("subproject")
    )]
    out={
        "request_id":rid,
        "project":start.get("project"),
        "subproject":start.get("subproject"),
        "started":start.get("time"),
    }
    for row in relevant:
        ev=row.get("event")
        if ev=="MOBILE_TASK_CONTEXT":
            out["context_ms"]=row.get("context_ms")
            out["scan_ms"]=row.get("scan_ms")
            out["scanned_files"]=row.get("scanned_files")
            out["scan_limited"]=row.get("scan_limited")
            out["context_files"]=row.get("context_files")
        elif ev=="MOBILE_TASK_JOB_DONE":
            out["done"]=row.get("time")
            out["duration_ms"]=row.get("duration_ms")
            out["state"]=row.get("state")
            out["status"]=row.get("status")
            out["error"]=row.get("error")
            out["detail"]=str(row.get("detail") or "")[:140]
        elif ev=="MOBILE_SUBTASK":
            out["engine"]=row.get("engine")
            out["model"]=row.get("model")
            out["execution_mode"]=row.get("execution_mode")
            out["files_changed"]=row.get("files_changed")
    return out


def _sanitize_diag_text(value):
    import re as _re
    s=str(value or "")
    s=_re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b","<ip>",s)
    s=_re.sub(r"[A-Za-z]:\\[^\\r\\n]+","<path>",s)
    return s[:180]

def _traceback_summaries(text,limit=8):
    out=[]
    for line in str(text or "").splitlines():
        s=line.strip()
        if not s or s.startswith("Traceback"):
            continue
        if ":" in s and (
            s.startswith(("OSError:","RuntimeError:","TimeoutError:","ConnectionError:","BrokenPipeError:",
                          "ConnectionResetError:","ValueError:","PermissionError:","FileNotFoundError:",
                          "urllib.error.","socket.","json."))
            or s.endswith("Error")
        ):
            clean=_sanitize_diag_text(s)
            if clean not in out:
                out.append(clean)
    return out[-limit:]

def _http_502_endpoints(text,limit=8):
    import re as _re
    counts={}
    for line in str(text or "").splitlines():
        m=_re.search(r'"(?:GET|POST|OPTIONS)\s+([^\s?"]+)(?:\?[^"]*)?\s+HTTP/[0-9.]+"\s+502\b',line)
        if m:
            path=m.group(1)
            counts[path]=counts.get(path,0)+1
    return sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))[:limit]


def _task_start_smoke():
    def one(base_url,label):
        rid="diag-go-"+label+"-"+str(int(time.time()*1000))
        payload={
            "project_id":"bazor-security",
            "subproject_name":"Diagnostic GO local",
            "task":"Diagnostic uniquement. Ne modifie aucun fichier. Termine par STATUS: OK, PROGRESS: 0, SUMMARY: test local, NEXT: aucun.",
            "current_progress":0,
            "repair":False,
            "previous":"",
            "provider":"ollama",
            "request_id":rid,
            "async":True,
            "apply_actions":False,
        }
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        req=urllib.request.Request(
            base_url+"/api/v1/task",
            data=data,
            headers={"Content-Type":"application/json"},
            method="POST",
        )
        started=time.monotonic()
        try:
            with urllib.request.urlopen(req,timeout=6.0) as r:
                raw=r.read().decode("utf-8","replace")
                status=getattr(r,"status",200)
            body=json.loads(raw) if raw else {}
            return {
                "ok":status in (200,202) and bool(body.get("ok")),
                "http":status,
                "job_state":body.get("job_state"),
                "request_id_match":body.get("request_id")==rid,
                "elapsed_ms":int((time.monotonic()-started)*1000),
            }
        except Exception as e:
            return {
                "ok":False,
                "error":type(e).__name__,
                "detail":_sanitize_diag_text(str(e)),
                "elapsed_ms":int((time.monotonic()-started)*1000),
            }
    return {
        "core8775":one("http://127.0.0.1:8775","core"),
        "gateway8776":one("http://127.0.0.1:8776","gateway"),
    }


def diagnostic_summary(force_usb=False, task_smoke=False):
    usb_result=None
    smoke_result=None
    if force_usb:
        usb_result=_force_usb_localhost(open_phone=True)
        time.sleep(1.5)
    if task_smoke:
        smoke_result=_task_start_smoke()

    data_dir=os.path.join(ROOT,"pc-relay","BAZOR_DATA")
    usb=_read_json(os.path.join(data_dir,"usb_android_status.json"))
    core_tail=_tail_text(os.path.join(HUB_LOG_DIR,"core.log"),500)
    web_tail=_tail_text(os.path.join(HUB_LOG_DIR,"web.log"),500)
    watcher_tail=_tail_text(os.path.join(HUB_LOG_DIR,"watcher.log"),500)
    selfheal_tail=_tail_text(os.path.join(HUB_LOG_DIR,"mobile_selfheal.log"),250)

    def count(text,needle):
        return text.lower().count(needle.lower())

    task=_latest_task_diag()
    tracebacks=_traceback_summaries(core_tail)
    ep502=_http_502_endpoints(web_tail)
    lines=[
        "**Diagnostic BAZOR local (résumé sans secrets)**",
        f"- Core 8775 local: {'OK' if _url_ok('http://127.0.0.1:8775/api/v1/security/status') else 'HS'}",
        f"- Gateway 8776 local: {'OK' if _url_ok('http://127.0.0.1:8776/api/v1/security/status') else 'HS'}",
        "- USB ADB: connected={0} reverse8775={1} reverse8776={2} reason={3}".format(
            bool(usb.get("connected")),bool(usb.get("core_reverse")),bool(usb.get("web_reverse")),usb.get("reason") or "none"
        ),
    ]
    if usb_result is not None:
        lines.append("- Forçage USB localhost: "+json.dumps(usb_result,ensure_ascii=False,separators=(",",":")))
    if smoke_result is not None:
        lines.append("- Smoke /api/v1/task: "+json.dumps(smoke_result,ensure_ascii=False,separators=(",",":")))
    if task:
        lines.append("- Dernière tâche GO: "+json.dumps(task,ensure_ascii=False,separators=(",",":")))
    lines += [
        "- core.log (500 lignes): traceback={0} reset={1} brokenpipe={2} reseau={3}".format(
            count(core_tail,"traceback"),count(core_tail,"connectionreset"),count(core_tail,"brokenpipe"),count(core_tail,"[reseau]")
        ),
        "- web.log (500 lignes): http502={0} gateway_unreachable={1} traceback={2}".format(
            count(web_tail,'" 502 ')+count(web_tail," 502 "),count(web_tail,"core_gateway_unreachable"),count(web_tail,"traceback")
        ),
        "- watcher.log (500 lignes): core_check={0} recovery={1} update={2}".format(
            count(watcher_tail,"[core check]"),count(watcher_tail,"[core recovery]"),count(watcher_tail,"[ok update]")
        ),
        "- selfheal.log: core_false={0} web_false={1} usb_false={2}".format(
            count(selfheal_tail,"core=false"),count(selfheal_tail,"web=false"),count(selfheal_tail,"usb=false")
        ),
        "- 502 par endpoint: "+(json.dumps(ep502,ensure_ascii=False,separators=(",",":")) if ep502 else "aucun"),
        "- Exceptions Core résumées: "+(json.dumps(tracebacks,ensure_ascii=False,separators=(",",":")) if tracebacks else "aucune"),
        "- Transport recommandé pour ce test: http://127.0.0.1:8776/ via ADB reverse (USB), pas l'adresse Wi-Fi."
    ]
    return "\n".join(lines)

def gh(args):
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    p=subprocess.run(["gh"]+args,capture_output=True,text=True,encoding="utf-8",errors="replace",creationflags=flags)
    if p.returncode: raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout

def core_chat(text):
    data=json.dumps({"text":text,"target":"ollama","room":"GITHUB QUEUE"}).encode("utf-8")
    req=urllib.request.Request(CORE,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))

def answer_text(result):
    o=result.get("ollama") or {}
    for k in ("response","answer","content","text"):
        if o.get(k): return str(o[k])
    return json.dumps(o,ensure_ascii=False,indent=2)[:12000]

if not _single_instance():
    print("[WATCHER] Une instance existe deja. Sortie sans relance.")
    raise SystemExit(0)

print("=== BAZOR GITHUB WATCHER V1 ===")
print("Repo :",REPO)
print("Core :",CORE)
print("Polling : 10 s")
print("Aucun shell distant : [bazor-queue] -> IA locale; [bazor-diag] -> diagnostic local predefini et filtre.")
print()

while True:
    try:
        safe_update()
        ensure_core_alive()
        try:
            issues=json.loads(gh(["issue","list","--repo",REPO,"--state","open","--limit","30","--json","number,title,body"]))
            for issue in issues:
                title=issue["title"].lower()
                comments=gh(["issue","view",str(issue["number"]),"--repo",REPO,"--comments"])
                if title.startswith("[bazor-diag]"):
                    if DIAG_MARK in comments: continue
                    print(f"[DIAG] #{issue['number']} {issue['title']}")
                    body=(issue.get("body") or "").lower()
                    reply=DIAG_MARK+"\n\n"+diagnostic_summary(force_usb=("usb" in body),task_smoke=("task-smoke" in body or "task smoke" in body))
                    gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply])
                    print(f"[OK DIAG] #{issue['number']} diagnostic retourne dans GitHub.")
                    continue
                if not title.startswith("[bazor-queue]"): continue
                if MARK in comments: continue
                print(f"[QUEUE] #{issue['number']} {issue['title']}")
                prompt=(issue.get("body") or "").strip()
                result=core_chat(prompt)
                reply=MARK+"\n\n**BAZOR/Ollama — résultat**\n\n"+answer_text(result)
                gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply])
                print(f"[OK] #{issue['number']} traite et retourne dans GitHub.")
        except Exception as e:
            print("[BLOQUE QUEUE]",type(e).__name__,str(e))
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print("[WATCHER RECOVERY]",type(e).__name__,str(e))
    time.sleep(POLL)
