import json, subprocess, time, urllib.request, os, sys, re, concurrent.futures

REPO="VincBZH/bazor-mobile"
COORD_REPO="VincBZH/projetWII-ai-relay"
CORE="http://127.0.0.1:8775/api/v1/chat"
CORE_HEALTH="http://127.0.0.1:8775/api/v1/security/status"
CORE_FAILS=0
PENDING_CORE_RESTART=False
POLL=10
MARK="[BAZOR-WATCHER-DONE]"
DIAG_MARK="[BAZOR-DIAG-DONE]"
MAMMOUTH_MARK="[BAZOR-MAMMOUTH-DONE]"
FILEBUS_MARK="[BAZOR-FILEBUS-DONE]"
TASK_MARK="[BAZOR-TASK-DONE]"
QUALIFY_MARK="[BAZOR-QUALIFY-DONE]"
CERTIFY_MARK="[BAZOR-CERTIFY-DONE]"
H3_AUDIT_MARK="[BAZOR-H3-AUDIT-DONE]"
WORKFLOWS_AUDIT_MARK="[BAZOR-WORKFLOWS-AUDIT-DONE]"
H3_CONVERTER_MARK="[BAZOR-H3-CONVERTER-DONE]"
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

def _parse_mammouth_issue(title, body):
    import re
    m=re.match(r"(?i)^\[bazor-mammouth(?::([a-z0-9._-]+))?\]", title or "")
    profile=(m.group(1).lower() if m and m.group(1) else "recommended")
    meta={"project":"simple-studio","subproject":"Revue Mammouth","profile":profile,"apply_actions":False}
    task_lines=[]
    for line in str(body or "").splitlines():
        s=line.strip()
        if ":" in s:
            k,v=s.split(":",1); lk=k.strip().lower(); val=v.strip()
            if lk=="project" and val: meta["project"]=val
            elif lk=="subproject" and val: meta["subproject"]=val
            elif lk=="profile" and val: meta["profile"]=val.lower()
            elif lk=="apply_actions": meta["apply_actions"]=val.lower() in ("1","true","yes","oui")
            elif lk=="task":
                if val: task_lines.append(val)
            else:
                task_lines.append(line)
        else:
            task_lines.append(line)
    meta["task"]="\n".join(x for x in task_lines if x.strip()).strip()
    return meta

def core_mammouth_task(title, body):
    meta=_parse_mammouth_issue(title, body)
    payload={
        "project_id":meta["project"],
        "subproject_name":meta["subproject"],
        "task":meta["task"] or "Faire une revue technique structurée du projet à partir du contexte local réel.",
        "current_progress":0,
        "repair":False,
        "previous":"",
        "provider":"mammouth",
        "mammouth_profile":meta["profile"],
        "apply_actions":bool(meta["apply_actions"]),
    }
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(
        "http://127.0.0.1:8775/api/v1/task",
        data=data,
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=260) as r:
        return json.loads(r.read().decode("utf-8"))

def _core_task(payload, timeout=420):
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(
        "http://127.0.0.1:8775/api/v1/task",
        data=data,
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _mobile_state_get():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8775/api/v1/mobile-state",timeout=5) as r:
            data=json.loads(r.read().decode("utf-8"))
        return data.get("state") or {}
    except Exception:
        return {}

def _mobile_state_put(state):
    data=json.dumps({"state":state},ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(
        "http://127.0.0.1:8775/api/v1/mobile-state",
        data=data,headers={"Content-Type":"application/json"},method="POST"
    )
    with urllib.request.urlopen(req,timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))

def _registry_task(task_id):
    path=os.path.join(ROOT,"bazor_registry.json")
    try:
        data=json.load(open(path,"r",encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("registry_unreadable: "+str(exc))
    wanted=str(task_id or "").strip().upper()
    for project in data.get("projects",[]):
        for task in project.get("tasks",[]):
            if str(task.get("id") or "").upper()==wanted:
                subs={x.get("id"):x for x in project.get("subprojects",[])}
                sub=subs.get(task.get("subproject")) or {}
                return project,task,sub
    raise RuntimeError("unknown_registry_task:"+wanted)

def _task_state_snapshot(project_id):
    state=_mobile_state_get()
    client=state.get("client_state") or {}
    return state,client,((client.get("taskStates") or {}).get(project_id) or {})

def _task_update_mobile(project, task, status, summary, result=None, reviews=None):
    state,client,_=_task_state_snapshot(project.get("id"))
    client.setdefault("taskStates",{})
    client["taskStates"].setdefault(project.get("id"),{})
    slot=client["taskStates"][project.get("id")].setdefault(task.get("id"),{})
    slot.update({
        "status":status,
        "summary":str(summary or "")[:1200],
        "updated":int(time.time()*1000),
        "last_engine":(result or {}).get("engine"),
        "last_model":(result or {}).get("model"),
        "reviews":reviews or [],
    })
    execution=(result or {}).get("execution") or {}
    ar=execution.get("action_result") or {}
    if execution.get("mode")=="file_changes" and ar.get("applied"):
        slot["evidence"]={
            "real":True,"when":int(time.time()*1000),
            "request_id":ar.get("request_id"),
            "files":ar.get("files") or [],
            "tests":ar.get("tests") or [],
            "preflight":ar.get("preflight"),
            "backup_dir":ar.get("backup_dir"),
            "report_file":ar.get("report_file"),
            "engine":(result or {}).get("engine"),
            "model":(result or {}).get("model"),
        }
    elif status=="VERIFIE":
        slot["evidence"]={
            "verified":True,"when":int(time.time()*1000),
            "engine":(result or {}).get("engine"),
            "model":(result or {}).get("model"),
            "context_files":((result or {}).get("local_context") or {}).get("files") or [],
        }
    else:
        slot["evidence"]=None

    # Mettre aussi à jour le statut projet pour que le résumé mobile soit cohérent.
    projects=client.setdefault("projects",[])
    pstate=next((x for x in projects if x.get("id")==project.get("id")),None)
    if pstate:
        task_states=client["taskStates"][project.get("id")]
        defs=project.get("tasks") or []
        done=sum(1 for x in defs if (task_states.get(x.get("id")) or {}).get("status") in ("DONE","VERIFIE"))
        pstate["progress"]=round(100*done/max(1,len(defs)))
        pstate["status"]="BLOQUE" if status=="BLOCKED" else ("OK" if done==len(defs) else "A_FAIRE")
        remaining=next((x for x in defs if (task_states.get(x.get("id")) or {}).get("status") not in ("DONE","VERIFIE")),None)
        pstate["next"]=(remaining or {}).get("title") or "Contrôle final"

    state["client_state"]=client
    state["taskboard_updated_at"]=time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        _mobile_state_put(state)
    except Exception as exc:
        print("[TASK STATE WARN]",type(exc).__name__,str(exc)[:180])

def _studio_p0_post_reviews(project, task, sub, base_prompt, execution_result):
    """Après une preuve locale, faire une revue croisée Claude/Gemini puis arbitrage GPT.
    Aucun reviewer externe n'écrit directement dans les fichiers.
    """
    execution=execution_result.get("execution") or {}
    ar=execution.get("action_result") or {}
    proof={
        "engine":execution_result.get("engine"),
        "model":execution_result.get("model"),
        "summary":str(execution_result.get("summary") or "")[:1200],
        "files":ar.get("files") or [],
        "tests":ar.get("tests") or [],
        "preflight":ar.get("preflight"),
        "report_file":ar.get("report_file"),
        "backup_dir":ar.get("backup_dir"),
    }
    proof_text=json.dumps(proof,ensure_ascii=False,separators=(",",":"))[:8000]
    review_prompt=(
        "REVUE POST-PATCH STUDIO V4. Ne modifie rien. Vérifie uniquement la preuve locale et le contexte réel. "
        "Réponds avec VERDICT: PASS ou VERDICT: BLOCK, puis BLOCKERS: et TESTS_MANQUANTS:. "
        "Ne bloque pas pour une simple préférence de style.\n\n"
        + base_prompt + "\n\nPREUVE_LOCALE:\n" + proof_text
    )

    def ask(profile):
        payload={
            "project_id":project.get("id"),
            "subproject_name":"Revue post-patch "+str(task.get("id")),
            "task":review_prompt,
            "current_progress":0,"repair":False,"previous":"",
            "provider":"mammouth","mammouth_profile":profile,"apply_actions":False,
        }
        try:
            rv=_core_task(payload,timeout=260)
            ans=str(rv.get("answer") or rv.get("summary") or "").strip()
            return {
                "profile":profile,"ok":bool(rv.get("ok") and ans),
                "engine":rv.get("engine"),"model":rv.get("model"),
                "answer":ans[:5000],
            }
        except Exception as exc:
            return {"profile":profile,"ok":False,"engine":"mammouth","model":None,
                    "answer":"","error":type(exc).__name__+": "+str(exc)[:300]}

    reviewers=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futs={p:pool.submit(ask,p) for p in ("claude","gemini")}
        for p in ("claude","gemini"):
            try: reviewers.append(futs[p].result())
            except Exception as exc:
                reviewers.append({"profile":p,"ok":False,"engine":"mammouth","model":None,
                                  "answer":"","error":type(exc).__name__+": "+str(exc)[:300]})

    useful="\n\n".join(
        "REVUE "+str(r.get("profile"))+" / "+str(r.get("model") or "?")+":\n"+str(r.get("answer") or "")
        for r in reviewers if r.get("ok")
    )
    arbiter_prompt=(
        "ARBITRAGE FINAL STUDIO V4. Tu es le reviewer GPT. Aucun accès shell, aucune écriture. "
        "Décide si la preuve locale + les revues permettent d'accepter la tâche. "
        "Réponds strictement avec VERDICT: PASS ou VERDICT: BLOCK, puis BLOCKERS: et NEXT:. "
        "Un avis externe indisponible ne doit pas bloquer si les tests déterministes et le runtime sont suffisants.\n\n"
        + base_prompt + "\n\nPREUVE_LOCALE:\n" + proof_text + "\n\n"
        + (useful or "AUCUNE_REVUE_EXTERNE_EXPLOITABLE")
    )
    arb_payload={
        "project_id":project.get("id"),
        "subproject_name":"Arbitrage GPT "+str(task.get("id")),
        "task":arbiter_prompt,
        "current_progress":0,"repair":False,"previous":"",
        "provider":"mammouth","mammouth_profile":"gpt","apply_actions":False,
    }
    try:
        arb=_core_task(arb_payload,timeout=260)
        arb_answer=str(arb.get("answer") or arb.get("summary") or "").strip()
        arb_ok=bool(arb.get("ok") and arb_answer)
    except Exception as exc:
        arb={"ok":False,"engine":"mammouth","model":"gpt-5.6-sol"}
        arb_answer=""
        arb_ok=False
        arb["error"]=type(exc).__name__+": "+str(exc)[:300]

    verdict=None
    if arb_ok:
        m=re.search(r"VERDICT\s*:\s*(PASS|BLOCK)",arb_answer,re.I)
        verdict=(m.group(1).upper() if m else None)

    return {
        "reviewers":reviewers,
        "arbiter":{
            "ok":arb_ok,"engine":arb.get("engine"),"model":arb.get("model"),
            "answer":arb_answer[:6000],"verdict":verdict,"error":arb.get("error")
        }
    }

def _studio_next_task(task_id):
    """Chaîne V4 prédéfinie. Aucun texte GitHub n'est exécuté comme commande."""
    chain={
        "STUDIO-P0-012":"STUDIO-P0-010",
        "STUDIO-P0-010":"STUDIO-P0-011",
    }
    return chain.get(str(task_id or "").upper())

def _studio_protocol_actions(task_id,result):
    """Interprète uniquement des règles locales statiques ; aucune commande n'est exécutée."""
    proto_dir=os.path.join(ROOT,"pc-relay","studio_v4_protocol")
    proto_file=os.path.join(proto_dir,"protocol.py")
    rules_file=os.path.join(proto_dir,"rules.json")
    if not (os.path.exists(proto_file) and os.path.exists(rules_file)):
        return []
    try:
        import importlib.util
        spec=importlib.util.spec_from_file_location("bazor_studio_v4_protocol",proto_file)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rules=mod.load_json(rules_file)
        ex=(result or {}).get("execution") or {}
        ar=ex.get("action_result") or {}
        tests=ar.get("tests") or []
        ctx={
            "task_id":str(task_id or "").upper(),
            "task_status":str((result or {}).get("task_status") or ""),
            "proof":{
                "preflight_ok":bool((ar.get("preflight") or {}).get("ok")),
                "tests_ok":bool(tests) and all(bool(x.get("ok")) for x in tests),
                "files_count":len(ar.get("files") or []),
            },
        }
        return mod.run_rules(rules,ctx)
    except Exception as exc:
        print("[PROTOCOL WARN]",type(exc).__name__,str(exc)[:240])
        return []

def _studio_protocol_next_task(task_id,result):
    for action in _studio_protocol_actions(task_id,result):
        if action.get("action")=="handoff":
            nxt=str(action.get("next_task") or "").strip().upper()
            if nxt in ("STUDIO-P0-010","STUDIO-P0-011"):
                return nxt
    return None

def _ensure_next_task_issue(current_task_id):
    next_id=_studio_next_task(current_task_id)
    if not next_id:
        return None
    try:
        existing=json.loads(gh([
            "issue","list","--repo",REPO,"--state","open","--limit","100",
            "--json","number,title"
        ]))
        needle="[bazor-task:"+next_id.lower()+"]"
        for item in existing:
            if str(item.get("title") or "").lower().startswith(needle):
                return int(item.get("number"))
        title="[bazor-task:"+next_id+"] AUTOCHAIN V4"
        body=(
            "AUTOCHAIN BAZOR V4.\n\n"
            "Tâche précédente validée: "+str(current_task_id)+".\n"
            "Exécuter maintenant la tâche prédéfinie "+next_id+" du registre BAZOR.\n"
            "Aucune commande shell libre n'est autorisée. Preflight, tests, preuves runtime "
            "et rollback restent obligatoires."
        )
        raw=gh(["issue","create","--repo",REPO,"--title",title,"--body",body])
        m=re.search(r"/issues/(\d+)",str(raw))
        return int(m.group(1)) if m else None
    except Exception as exc:
        print("[AUTOCHAIN WARN]",type(exc).__name__,str(exc)[:240])
        return None

def _run_registry_task(task_id):
    project,task,sub=_registry_task(task_id)
    if project.get("go_compatible") is False:
        return {"ok":False,"task_status":"BLOCKED","error":"project_not_executable","detail":project.get("go_reason") or ""}

    state,client,task_states=_task_state_snapshot(project.get("id"))
    missing=[dep for dep in task.get("dependencies",[]) if (task_states.get(dep) or {}).get("status") not in ("DONE","VERIFIE")]
    if missing:
        detail="Dépendances non terminées: "+", ".join(missing)
        _task_update_mobile(project,task,"BLOCKED",detail)
        return {"ok":False,"task_status":"BLOCKED","error":"dependencies_not_done","detail":detail}

    studio_p0_fast=(project.get("id")=="simple-studio" and task.get("priority")=="P0")
    _task_update_mobile(
        project,task,"RUNNING",
        "Tâche Studio P0 locale démarrée • Ollama + Action Engine"
        if studio_p0_fast else
        "Tâche autonome démarrée • secondes lectures Mammouth en cours"
    )
    criteria="\n".join(f"{i+1}. {x}" for i,x in enumerate(task.get("acceptance") or []))
    base_prompt=(
        "TÂCHE BAZOR PRÉDÉFINIE "+str(task.get("id"))+" — "+str(task.get("title"))+"\n"
        "ACTION ATTENDUE:\n"+str(task.get("action") or "")+"\n"
        "CRITÈRES DE DONE:\n"+criteria+"\n"
        "RÈGLE DE PREUVE: "+str(task.get("proof_required") or "file_changes_and_tests")+"\n"
        "Si les critères sont déjà satisfaits dans les fichiers réellement lus et qu’aucune modification n’est nécessaire, "
        "n’invente aucun changement et commence SUMMARY par DEJA_CONFORME:. Sinon, propose uniquement des BAZOR_ACTIONS minimales, ciblées et vérifiables."
    )

    reviews=[]
    # Fast-path Studio P0 : aucune revue externe avant l'exécution locale.
    # Elles pourront être faites après une preuve locale, sans bloquer le patch.
    profiles=[] if studio_p0_fast else [str(x).lower() for x in (task.get("preferred_models") or []) if str(x).strip()]
    profiles=profiles[:2 if task.get("priority")=="P0" else 1]

    def one_review(profile):
        review_payload={
            "project_id":project.get("id"),
            "subproject_name":"Revue "+str(task.get("id"))+" / "+str(sub.get("name") or task.get("subproject") or "Studio"),
            "task":"SECONDE LECTURE MAMMOUTH. Ne modifie rien et n'émets pas BAZOR_ACTIONS. "
                   "Donne seulement les constats confirmés dans les fichiers, risques, correctif minimal et tests.\n\n"+base_prompt,
            "current_progress":0,"repair":False,"previous":"",
            "provider":"mammouth","mammouth_profile":profile,"apply_actions":False,
        }
        try:
            rv=_core_task(review_payload,timeout=300)
            return {
                "profile":profile,"ok":bool(rv.get("ok")),
                "engine":rv.get("engine"),"model":rv.get("model"),
                "summary":str(rv.get("summary") or "")[:500],
                "answer":str(rv.get("answer") or "")[:3500],
            }
        except Exception as exc:
            return {"profile":profile,"ok":False,"engine":"mammouth","model":None,"summary":str(exc)[:300],"answer":""}

    # Les avis sont indépendants et non-écrivants : les lancer en parallèle
    # évite de doubler le temps d'attente d'une tâche P0.
    if profiles:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(2,len(profiles))) as pool:
            future_by_profile={pool.submit(one_review,p):p for p in profiles}
            by_profile={}
            for fut,p in list(future_by_profile.items()):
                try:
                    by_profile[p]=fut.result()
                except Exception as exc:
                    by_profile[p]={"profile":p,"ok":False,"engine":"mammouth","model":None,"summary":str(exc)[:300],"answer":""}
            reviews=[by_profile[p] for p in profiles]

    useful=[]
    for rv in reviews:
        if rv.get("ok") and rv.get("answer"):
            useful.append("AVIS "+str(rv.get("profile"))+" (modèle réel: "+str(rv.get("model") or rv.get("engine") or "?")+"):\n"+str(rv.get("answer"))[:2500])
    final_prompt=base_prompt
    if useful:
        final_prompt+="\n\nSECOND AVIS À PRENDRE EN COMPTE SANS LE SUIVRE AVEUGLÉMENT:\n"+"\n\n".join(useful)

    # Studio P0 doit commencer localement: le code cible vit sur le PC et
    # Ollama + Action Engine peuvent lire/preflight/tester sans dépendre d'un
    # fournisseur externe. Les revues Mammouth restent consultatives.
    execution_provider="ollama" if studio_p0_fast else "auto"
    payload={
        "project_id":project.get("id"),
        "subproject_name":str(task.get("id"))+" / "+str(sub.get("name") or task.get("subproject") or "Studio"),
        "task":final_prompt,
        "current_progress":0,"repair":False,"previous":"",
        "provider":execution_provider,"apply_actions":True,
    }
    task_timeout=300 if studio_p0_fast else 420
    result=_core_task(payload,timeout=task_timeout)
    execution=result.get("execution") or {}
    ar=execution.get("action_result") or {}
    real=execution.get("mode")=="file_changes" and bool(ar.get("applied"))
    tests=ar.get("tests") or []
    tests_ok=all(x.get("ok") for x in tests)
    text=(str(result.get("summary") or "")+"\n"+str(result.get("answer") or ""))
    already=bool(re.search(r"DEJA_CONFORME\s*:",text,re.I))
    blocked=(result.get("status")=="BLOQUE") or (not result.get("ok"))

    # Si AUTO choisit un moteur externe indisponible ou renvoie BLOQUE sans
    # modification/preflight, ne pas arrêter une tâche Studio exécutable.
    # Rejouer une fois avec Ollama local, qui possède l'accès au contexte local
    # via BAZOR Core/Action Engine. Les tests/preflight restent l'arbitre final.
    if blocked and not real and not already and not studio_p0_fast:
        local_retry=dict(payload)
        local_retry["provider"]="ollama"
        local_retry["repair"]=True
        local_retry["previous"]=str(result.get("answer") or result.get("detail") or "")[:5000]
        try:
            local_result=_core_task(local_retry,timeout=420)
            local_execution=local_result.get("execution") or {}
            local_ar=local_execution.get("action_result") or {}
            local_real=local_execution.get("mode")=="file_changes" and bool(local_ar.get("applied"))
            local_tests=local_ar.get("tests") or []
            local_tests_ok=all(x.get("ok") for x in local_tests)
            local_text=(str(local_result.get("summary") or "")+"\n"+str(local_result.get("answer") or ""))
            local_already=bool(re.search(r"DEJA_CONFORME\s*:",local_text,re.I))
            local_blocked=(local_result.get("status")=="BLOQUE") or (not local_result.get("ok"))
            # Préférer le résultat local s'il progresse réellement ou fournit
            # une preuve exploitable. Ne jamais remplacer un résultat plus riche
            # par un simple échec générique.
            if local_real or local_already or (not local_blocked and local_text.strip()):
                result=local_result
                execution=local_execution
                ar=local_ar
                real=local_real
                tests=local_tests
                tests_ok=local_tests_ok
                text=local_text
                already=local_already
                blocked=local_blocked
        except Exception as local_exc:
            reviews.append({
                "profile":"local-fallback",
                "ok":False,
                "engine":"ollama",
                "model":None,
                "summary":type(local_exc).__name__+": "+str(local_exc)[:260],
                "answer":"",
            })

    # Une première analyse seule n'est pas un succès : une seule relance explicite.
    if not real and not already and not blocked and not studio_p0_fast:
        retry=dict(payload)
        retry["repair"]=True
        retry["previous"]=str(result.get("answer") or "")[:5000]
        result=_core_task(retry,timeout=420)
        execution=result.get("execution") or {}
        ar=execution.get("action_result") or {}
        real=execution.get("mode")=="file_changes" and bool(ar.get("applied"))
        tests=ar.get("tests") or []
        tests_ok=all(x.get("ok") for x in tests)
        text=(str(result.get("summary") or "")+"\n"+str(result.get("answer") or ""))
        already=bool(re.search(r"DEJA_CONFORME\s*:",text,re.I))
        blocked=(result.get("status")=="BLOQUE") or (not result.get("ok"))

    trio_review=None
    if studio_p0_fast and ((real and tests_ok) or (already and not blocked)):
        trio_review=_studio_p0_post_reviews(project,task,sub,base_prompt,result)
        reviews.extend(trio_review.get("reviewers") or [])
        arb=(trio_review.get("arbiter") or {})
        reviews.append({
            "profile":"gpt-arbiter","ok":bool(arb.get("ok")),
            "engine":arb.get("engine"),"model":arb.get("model"),
            "summary":("VERDICT: "+str(arb.get("verdict") or "INCONNU"))[:300],
            "answer":str(arb.get("answer") or "")[:3500],
        })

        # Un seul cycle de réparation locale si GPT identifie un bloqueur réel.
        if arb.get("verdict")=="BLOCK":
            repair_payload=dict(payload)
            repair_payload["repair"]=True
            repair_payload["previous"]=str(arb.get("answer") or "")[:5000]
            repair_payload["task"]=base_prompt+"\n\nREVUE GPT À CORRIGER:\n"+str(arb.get("answer") or "")[:5000]
            try:
                repaired=_core_task(repair_payload,timeout=300)
                rex=repaired.get("execution") or {}
                rar=rex.get("action_result") or {}
                rreal=rex.get("mode")=="file_changes" and bool(rar.get("applied"))
                rtests=rar.get("tests") or []
                rtests_ok=all(x.get("ok") for x in rtests)
                rtext=(str(repaired.get("summary") or "")+"\n"+str(repaired.get("answer") or ""))
                ralready=bool(re.search(r"DEJA_CONFORME\s*:",rtext,re.I))
                rblocked=(repaired.get("status")=="BLOQUE") or (not repaired.get("ok"))
                if (rreal and rtests_ok) or (ralready and not rblocked):
                    result=repaired; execution=rex; ar=rar
                    real=rreal; tests=rtests; tests_ok=rtests_ok
                    text=rtext; already=ralready; blocked=rblocked
                    trio_review=_studio_p0_post_reviews(project,task,sub,base_prompt,result)
                    reviews.extend(trio_review.get("reviewers") or [])
                    arb=(trio_review.get("arbiter") or {})
            except Exception as repair_exc:
                blocked=True
                reviews.append({"profile":"local-repair","ok":False,"engine":"ollama","model":None,
                                "summary":type(repair_exc).__name__+": "+str(repair_exc)[:300],"answer":""})

    final_arb=(trio_review or {}).get("arbiter") or {}
    arb_blocks=(final_arb.get("verdict")=="BLOCK")

    if real and tests_ok and not arb_blocks:
        task_status="DONE"; summary=str(result.get("summary") or "Correction appliquée et testée")
    elif already and not blocked and not arb_blocks:
        task_status="VERIFIE"; summary=str(result.get("summary") or "Déjà conforme vérifié")
    elif blocked or arb_blocks:
        task_status="BLOCKED"; summary=str(result.get("summary") or result.get("detail") or "Blocage")
    else:
        task_status="ANALYSE_SEULE"; summary="ANALYSE SEULE — aucune modification prouvée"

    _task_update_mobile(project,task,task_status,summary,result=result,reviews=reviews)
    return {
        "ok":task_status in ("DONE","VERIFIE"),
        "task_id":task.get("id"),"task_status":task_status,
        "summary":summary,"engine":result.get("engine"),"model":result.get("model"),
        "reviews":reviews,"execution":execution,
        "answer":str(result.get("answer") or "")[:7000],
    }

def _run_studio_qualification():
    script=os.path.join(ROOT,"pc-relay","bazor_studio_qualifier.py")
    if not os.path.exists(script): return {"ok":False,"error":"qualifier_missing","detail":script}
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    try:
        cp=subprocess.run([sys.executable,script,"--compact"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=900,creationflags=flags)
    except Exception as exc:
        return {"ok":False,"error":type(exc).__name__,"detail":str(exc)[:1200]}
    latest=os.path.join(ROOT,"pc-relay","BAZOR_DATA","STUDIO_QUALIFICATION","latest.json")
    try: report=json.load(open(latest,"r",encoding="utf-8"))
    except Exception as exc: return {"ok":False,"error":"report_unreadable","detail":str(exc)[:1000],"stdout":cp.stdout[-4000:],"stderr":cp.stderr[-4000:]}
    summary=report.get("summary") or {}; failures=[x for x in report.get("results",[]) if not x.get("ok")]
    return {"ok":bool(summary.get("operational")),"returncode":cp.returncode,"summary":summary,"failures":failures,"report_file":latest,"stdout":cp.stdout[-5000:],"stderr":cp.stderr[-3000:]}

def _run_studio_certified_test():
    cmd=os.path.join(ROOT,"LANCER_BAZOR_STUDIO_CERTIFIE.cmd")
    if os.name!="nt":
        return {"ok":False,"returncode":96,"stdout":"","stderr":"windows_required"}
    if not os.path.exists(cmd):
        return {"ok":False,"returncode":98,"stdout":"","stderr":"certified_cmd_missing"}
    env=os.environ.copy()
    env["BAZOR_STUDIO_TEST_ONLY"]="1"
    env["BAZOR_STUDIO_NO_PAUSE"]="1"
    try:
        cp=subprocess.run(
            ["cmd","/c",cmd],
            cwd=ROOT,env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",
            timeout=300,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        )
        return {"ok":cp.returncode==0,"returncode":cp.returncode,"stdout":cp.stdout[-10000:],"stderr":cp.stderr[-4000:]}
    except Exception as exc:
        return {"ok":False,"returncode":97,"stdout":"","stderr":type(exc).__name__+": "+str(exc)}


def _run_h3_connection_audit():
    script=os.path.join(ROOT,"pc-relay","bazor_h3_connection_audit.py")
    if not os.path.exists(script):
        return {"ok":False,"error":"audit_missing"}
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    try:
        cp=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=180,creationflags=flags)
    except Exception as exc:
        return {"ok":False,"error":type(exc).__name__,"detail":str(exc)[:800]}
    latest=os.path.join(ROOT,"pc-relay","BAZOR_DATA","H3_CONNECTION_AUDIT","latest.json")
    try:
        data=json.load(open(latest,"r",encoding="utf-8"))
    except Exception as exc:
        return {"ok":False,"error":"report_unreadable","detail":str(exc)[:800],"stdout":cp.stdout[-3000:],"stderr":cp.stderr[-2000:]}
    return {"ok":cp.returncode==0,"report":data,"stdout":cp.stdout[-3000:],"stderr":cp.stderr[-2000:]}

def _run_workflows_audit():
    script=os.path.join(ROOT,"pc-relay","bazor_studio_workflows_audit.py")
    if not os.path.exists(script):
        return {"ok":False,"error":"audit_missing"}
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    cp=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=90,creationflags=flags)
    latest=os.path.join(ROOT,"pc-relay","BAZOR_DATA","STUDIO_WORKFLOWS_AUDIT","latest.json")
    try:
        report=json.load(open(latest,"r",encoding="utf-8"))
    except Exception as exc:
        return {"ok":False,"error":"report_unreadable","detail":str(exc)[:800],"stdout":cp.stdout[-2000:],"stderr":cp.stderr[-2000:]}
    return {"ok":cp.returncode==0,"report":report,"stdout":cp.stdout[-2000:],"stderr":cp.stderr[-2000:]}

def _run_h3_converter_hotfix():
    script=os.path.join(ROOT,"pc-relay","bazor_studio_h3_converter_hotfix.py")
    if not os.path.exists(script):
        return {"ok":False,"error":"hotfix_missing"}
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    try:
        cp=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=180,creationflags=flags)
    except Exception as exc:
        return {"ok":False,"error":type(exc).__name__,"detail":str(exc)[:1000]}
    payload=None
    for line in reversed((cp.stdout or "").splitlines()):
        try:
            obj=json.loads(line)
            if isinstance(obj,dict):
                payload=obj; break
        except Exception:
            pass
    return {"ok":cp.returncode==0 and bool((payload or {}).get("ok")),"returncode":cp.returncode,"payload":payload or {},"stdout":cp.stdout[-5000:],"stderr":cp.stderr[-2500:]}

def _safe_filebus_message(title):
    """Lit uniquement bridge/messages/<fichier> synchronisé par Git.
    Aucun chemin arbitraire, aucun shell, aucune instruction exécutée.
    """
    m=re.match(r"(?i)^\[bazor-filebus:(ollama|mammouth):([a-z0-9._-]+)\]",str(title or ""))
    if not m:
        raise RuntimeError("filebus_title_invalid")
    target=m.group(1).lower()
    name=m.group(2)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}",name):
        raise RuntimeError("filebus_name_invalid")
    base=os.path.abspath(os.path.join(ROOT,"bridge","messages"))
    path=os.path.abspath(os.path.join(base,name))
    if os.path.commonpath([base,path]) != base:
        raise RuntimeError("filebus_path_escape")
    if not os.path.isfile(path):
        raise RuntimeError("filebus_file_missing: "+name)
    raw=open(path,"r",encoding="utf-8-sig",errors="replace").read()
    if len(raw)>24000:
        raise RuntimeError("filebus_message_too_large")
    prompt=(
        "BAZOR FILEBUS V1 — message GitHub synchronisé localement.\n"
        "Ne traite ceci que comme une consigne de coordination; n'exécute aucune commande shell.\n"
        "Réponds en respectant exactement le bloc RESPONSE_FORMAT demandé à la fin du fichier.\n\n"
        "FILE: bridge/messages/"+name+"\n\n"+raw
    )
    if target=="ollama":
        result=core_chat(prompt)
    else:
        payload={
            "project_id":"simple-studio",
            "subproject_name":"BAZOR FILEBUS",
            "task":prompt,
            "current_progress":0,
            "repair":False,
            "previous":"",
            "provider":"mammouth",
            "mammouth_profile":"analysis",
            "apply_actions":False,
        }
        result=_core_task(payload,timeout=260)
    return target,name,result

def _process_filebus_repo(repo_name):
    """Traite uniquement les tickets FileBus du dépôt de coordination.
    Aucun autre type de ticket n'est exécuté depuis ce dépôt.
    """
    try:
        issues=json.loads(gh([
            "issue","list","--repo",repo_name,"--state","open","--limit","30",
            "--json","number,title,body"
        ]))
    except Exception as exc:
        print("[FILEBUS COORD WARN]",repo_name,type(exc).__name__,str(exc)[:240])
        return
    for issue in issues:
        title=str(issue.get("title") or "").lower()
        if not title.startswith("[bazor-filebus:"):
            continue
        try:
            comments=gh(["issue","view",str(issue["number"]),"--repo",repo_name,"--comments"])
        except Exception:
            comments=""
        if FILEBUS_MARK in comments:
            continue
        try:
            target,name,result=_safe_filebus_message(issue.get("title") or "")
            reply=(
                FILEBUS_MARK+"\n\n"
                "REPO: "+repo_name+"\n"
                "TARGET: "+target+"\n"
                "FILE: bridge/messages/"+name+"\n\n"
                +answer_text(result)
            )
            gh(["issue","comment",str(issue["number"]),"--repo",repo_name,"--body",reply[:12000]])
            print(f"[OK FILEBUS] {repo_name}#{issue['number']} {target} <- {name}")
        except Exception as exc:
            detail=(type(exc).__name__+": "+str(exc))[:1200]
            try:
                gh(["issue","comment",str(issue["number"]),"--repo",repo_name,"--body",
                    FILEBUS_MARK+"\n\nSTATUS: BLOCKED\nERROR: "+detail])
            except Exception:
                pass
            print(f"[BLOQUE FILEBUS] {repo_name}#{issue['number']} {detail}")

def answer_text(result):
    for section in ("mammouth","ollama"):
        o=result.get(section) or {}
        for k in ("response","answer","content","text"):
            if o.get(k): return str(o[k])
    for k in ("answer","message","summary","detail"):
        if result.get(k): return str(result[k])
    return json.dumps(result,ensure_ascii=False,indent=2)[:12000]

if not _single_instance():
    print("[WATCHER] Une instance existe deja. Sortie sans relance.")
    raise SystemExit(0)

print("=== BAZOR GITHUB WATCHER V1 ===")
print("Repo :",REPO)
print("Core :",CORE)
print("Polling : 10 s")
print("Aucun shell distant : [bazor-task:ID] -> tâche prédéfinie + sandbox; [bazor-mammouth:profil] -> revue; [bazor-queue] -> IA locale; [bazor-diag] -> diagnostic.")
print()

while True:
    try:
        safe_update()
        ensure_core_alive()
        _process_filebus_repo(COORD_REPO)
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
                if title.startswith("[bazor-hotfix:h3-ui-api]"):
                    if H3_CONVERTER_MARK in comments:
                        continue
                    result=_run_h3_converter_hotfix()
                    payload=result.get("payload") or {}
                    lines=[
                        H3_CONVERTER_MARK,"","**BAZOR Studio — hotfix UI → API H3**","",
                        "Statut: "+("PASS" if result.get("ok") else "FAIL"),
                        "Code: "+str(result.get("returncode")),
                        "État: "+str(payload.get("state") or "?"),
                        "Modifié: "+str(payload.get("changed")),
                        "Rapport: "+str(payload.get("report") or "?"),
                        "Test: "+json.dumps(payload.get("unit_test") or {},ensure_ascii=False),
                    ]
                    if result.get("stderr"):
                        lines += ["","stderr:",str(result.get("stderr"))[-1800:]]
                    try:
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","\n".join(lines)[:12000]])
                    except Exception:
                        pass
                    continue
                if title.startswith("[bazor-workflows-audit]"):
                    if WORKFLOWS_AUDIT_MARK in comments:
                        continue
                    result=_run_workflows_audit()
                    report=result.get("report") or {}
                    lines=[WORKFLOWS_AUDIT_MARK,"","**BAZOR Studio — audit workflows.py**","",
                           "Statut: "+("PASS" if result.get("ok") else "FAIL"),
                           "Fichier: "+str(report.get("path") or "?"),""]
                    for ex in report.get("excerpts") or []:
                        lines.append(f"--- lignes {ex.get('start')}-{ex.get('end')} ---")
                        for row in ex.get("lines") or []:
                            lines.append(f"L{row.get('line')}: {str(row.get('text') or '')[:1000]}")
                    if result.get("stderr"):
                        lines += ["","stderr:",str(result.get("stderr"))[-1200:]]
                    try:
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","\n".join(lines)[:12000]])
                    except Exception:
                        pass
                    continue
                if title.startswith("[bazor-h3-audit]"):
                    if H3_AUDIT_MARK in comments:
                        continue
                    result=_run_h3_connection_audit()
                    report=result.get("report") or {}
                    workflows=report.get("workflows") or []
                    bad=sum(len(x.get("bad_values") or []) for x in workflows)
                    dims=sum(len(x.get("dimensions") or []) for x in workflows)
                    refs=report.get("active_refs") or []
                    lines=[
                        H3_AUDIT_MARK,"","**BAZOR H3 — audit connexions**","",
                        "Statut: "+("PASS" if result.get("ok") else "FAIL"),
                        f"Workflows H3: {len(workflows)}",
                        f"Valeurs loader invalides trouvées dans workflow: {bad}",
                        f"Champs dimensions détectés: {dims}",
                        f"Fichiers Studio liés: {len(refs)}",""
                    ]
                    for wf in workflows[:5]:
                        lines.append("Workflow: "+str(wf.get("path")))
                        for x in wf.get("bad_values") or []:
                            lines.append("  BAD "+str(x.get("input"))+": "+str(x.get("bad"))+" -> "+str(x.get("replacement"))+" @ node "+str(x.get("node_id")))
                        for x in (wf.get("dimensions") or [])[:12]:
                            lines.append("  DIM node "+str(x.get("node_id"))+" "+str(x.get("class_type"))+"."+str(x.get("input"))+"="+str(x.get("value")))
                        graph=wf.get("ui_graph") or {}
                        if graph.get("format")=="ui":
                            lines.append("  UI GRAPH nodes="+str(len(graph.get("nodes") or []))+" links="+str(len(graph.get("links") or [])))
                            interesting=[]
                            keys=("clip","vae","unet","latent","video","image","size","resolution","width","height","empty","sampler","save","preview","h3")
                            for node in graph.get("nodes") or []:
                                blob=(" ".join([str(node.get("type") or ""),str(node.get("title") or "")])).lower()
                                if any(k in blob for k in keys):
                                    interesting.append(node)
                            for node in interesting[:40]:
                                widgets=node.get("widgets_values")
                                if isinstance(widgets,list):
                                    widgets=widgets[:12]
                                lines.append("  NODE "+str(node.get("id"))+" "+str(node.get("type"))+" title="+str(node.get("title") or "")+" widgets="+json.dumps(widgets,ensure_ascii=False)[:900])
                                if node.get("inputs"):
                                    lines.append("    IN "+json.dumps(node.get("inputs"),ensure_ascii=False,separators=(",",":"))[:1000])
                                if node.get("outputs"):
                                    lines.append("    OUT "+json.dumps(node.get("outputs"),ensure_ascii=False,separators=(",",":"))[:1000])
                    for rf in refs[:12]:
                        lines.append("REF "+str(rf.get("path")))
                        for ln in (rf.get("lines") or [])[:8]:
                            lines.append("  L"+str(ln.get("line"))+": "+str(ln.get("text")))
                    if result.get("stderr"):
                        lines += ["","stderr:",str(result.get("stderr"))[-1500:]]
                    try:
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","\n".join(lines)[:12000]])
                    except Exception:
                        pass
                    continue
                if title.startswith("[bazor-certify:studio]"):
                    if CERTIFY_MARK in comments:
                        continue
                    print(f"[CERTIFY] #{issue['number']} Studio certified launcher")
                    result=_run_studio_certified_test()
                    reply=CERTIFY_MARK+"\n\n**BAZOR Studio — test du lanceur certifié**\n\nStatut: "+("PASS" if result.get("ok") else "FAIL")+"\nCode: "+str(result.get("returncode"))+"\n\n"+str(result.get("stdout") or "")[-7000:]
                    if result.get("stderr"):
                        reply+="\n\nstderr:\n"+str(result.get("stderr"))[-2500:]
                    try:
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply[:12000]])
                    except Exception:
                        pass
                    continue
                if title.startswith("[bazor-qualify:studio]"):
                    if QUALIFY_MARK in comments: continue
                    print(f"[QUALIFY] #{issue['number']} Studio qualification")
                    try:
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","[BAZOR-QUALIFY-START]\n\nQualification complète AI Simple Studio démarrée sur le PC local. Aucun fichier Studio n’est modifié par ce test."])
                    except Exception: pass
                    result=_run_studio_qualification(); s=result.get("summary") or {}; fails=result.get("failures") or []
                    lines=[QUALIFY_MARK,"","**BAZOR Studio — qualification locale**","",f"Résultat: {'OPÉRATIONNEL' if result.get('ok') else 'NON OPÉRATIONNEL'}",f"Tests: {s.get('passed',0)}/{s.get('total',0)} • {s.get('percent',0)}%",f"Échecs: P0={s.get('p0_failed',0)} • P1={s.get('p1_failed',0)} • P2={s.get('p2_failed',0)}",""]
                    if fails:
                        lines.append("**Échecs détectés**")
                        for x in fails[:35]:
                            ev=json.dumps(x.get("evidence") or {},ensure_ascii=False,separators=(",",":"))
                            lines.append(f"- {x.get('severity')} {x.get('id')} — {x.get('name')}: {str(x.get('detail') or '')[:700]} • evidence={ev[:1200]}")
                    else: lines.append("Aucun échec détecté.")
                    lines += ["","Rapport local: "+str(result.get("report_file") or "?")]
                    if result.get("stderr"): lines += ["","stderr (fin):",str(result.get("stderr"))[-2000:]]
                    try: gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","\n".join(lines)[:12000]])
                    except Exception: pass
                    print(f"[OK QUALIFY] #{issue['number']} operational={result.get('ok')} failures={len(fails)}")
                    continue
                if title.startswith("[bazor-task:"):
                    if TASK_MARK in comments: continue
                    m=re.match(r"(?i)^\[bazor-task:([^\]]+)\]",issue.get("title") or "")
                    if not m:
                        continue
                    task_id=m.group(1).strip().upper()
                    print(f"[TASK] #{issue['number']} {task_id}")
                    try:
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","[BAZOR-TASK-START]\n\n"+task_id+" démarrée. État mobile passé EN COURS ; secondes lectures puis préflight Git avant toute écriture."])
                    except Exception:
                        pass
                    try:
                        result=_run_registry_task(task_id)
                        ex=result.get("execution") or {}; ar=ex.get("action_result") or {}
                        pre=(ar.get("preflight") or {})
                        proof=(
                            f"\n\nPreflight sandbox: {'OK' if pre.get('ok') else '—'}"
                            f"\nFichiers modifiés: {len(ar.get('files') or [])}"
                            f"\nTests cible: {sum(1 for x in (ar.get('tests') or []) if x.get('ok'))}/{len(ar.get('tests') or [])}"
                        )
                        review_lines="\n".join(
                            "- "+str(x.get("profile"))+" → "+str(x.get("model") or x.get("engine") or "?")+" : "+("OK" if x.get("ok") else "HS")
                            for x in result.get("reviews") or []
                        )
                        reply=TASK_MARK+"\n\n**BAZOR Task — "+task_id+"**\n\nStatut: "+str(result.get("task_status"))+"\nRésumé: "+str(result.get("summary") or "")+proof
                        if review_lines:
                            reply+="\n\nSecondes lectures:\n"+review_lines
                        reply+="\n\nMoteur final: "+str(result.get("engine") or "?")+" / "+str(result.get("model") or "?")
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply[:12000]])
                        print(f"[OK TASK] #{issue['number']} {task_id} -> {result.get('task_status')}")
                        if result.get("task_status") in ("DONE","VERIFIE"):
                            protocol_next=_studio_protocol_next_task(task_id,result)
                            expected_next=_studio_next_task(task_id)
                            if protocol_next and protocol_next==expected_next:
                                next_issue=_ensure_next_task_issue(task_id)
                                if next_issue:
                                    chain_msg="[BAZOR-AUTOCHAIN]\n\nProtocole validé : preflight + tests OK. Étape suivante créée automatiquement: #"+str(next_issue)+" • "+str(protocol_next)
                                    try:
                                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",chain_msg])
                                    except Exception:
                                        pass
                            else:
                                try:
                                    gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body","[BAZOR-AUTOCHAIN-BLOCKED]\n\nAucun handoff : le protocole local n'a pas validé preflight + tests."])
                                except Exception:
                                    pass
                    except Exception as task_exc:
                        detail=(type(task_exc).__name__+": "+str(task_exc))[:1200]
                        try:
                            project,task,_=_registry_task(task_id)
                            _task_update_mobile(project,task,"BLOCKED","Exception tâche autonome: "+detail)
                        except Exception:
                            pass
                        reply=TASK_MARK+"\n\n**BAZOR Task — "+task_id+"**\n\nStatut: BLOCKED\nErreur interne capturée: "+detail
                        try:
                            gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply])
                        except Exception:
                            pass
                        print(f"[BLOQUE TASK] #{issue['number']} {task_id} {detail}")
                    continue
                if title.startswith("[bazor-filebus:"):
                    if FILEBUS_MARK in comments:
                        continue
                    try:
                        target,name,result=_safe_filebus_message(issue.get("title") or "")
                        reply=(
                            FILEBUS_MARK+"\n\n"
                            "TARGET: "+target+"\n"
                            "FILE: bridge/messages/"+name+"\n\n"
                            +answer_text(result)
                        )
                        gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply[:12000]])
                        print(f"[OK FILEBUS] #{issue['number']} {target} <- {name}")
                    except Exception as exc:
                        detail=(type(exc).__name__+": "+str(exc))[:1200]
                        try:
                            gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",
                                FILEBUS_MARK+"\n\nSTATUS: BLOCKED\nERROR: "+detail])
                        except Exception:
                            pass
                        print(f"[BLOQUE FILEBUS] #{issue['number']} {detail}")
                    continue
                if title.startswith("[bazor-mammouth"):
                    if MAMMOUTH_MARK in comments: continue
                    print(f"[MAMMOUTH] #{issue['number']} {issue['title']}")
                    result=core_mammouth_task(issue.get("title") or "", issue.get("body") or "")
                    route=result.get("route") or {}
                    model=result.get("model") or route.get("profile") or "mammouth"
                    reply=MAMMOUTH_MARK+"\n\n**BAZOR/Mammouth — résultat**\n\nProfil: "+str(model)+"\n\n"+answer_text(result)
                    gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply])
                    print(f"[OK MAMMOUTH] #{issue['number']} traite et retourne dans GitHub.")
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
