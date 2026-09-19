from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOCALAPP=Path(os.environ.get("LOCALAPPDATA") or (Path.home()/"AppData"/"Local"))
ROOM=LOCALAPP/"BazorAIROOM"
CONTROL=ROOM/"control.json"
WATCHER=ROOT/"pc-relay"/"bazor_github_watcher.py"
LOG=ROOM/"oneshot_recovery.log"

def log(msg):
    ROOM.mkdir(parents=True,exist_ok=True)
    line=time.strftime("%Y-%m-%d %H:%M:%S")+" "+msg
    print(line,flush=True)
    with LOG.open("a",encoding="utf-8") as h:h.write(line+"\n")

def run(args,timeout=60):
    return subprocess.run(args,cwd=str(ROOT),capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout,
                          creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))

def http(port,path="/health",timeout=2):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except Exception as e:
        return None, type(e).__name__+": "+str(e)

def watcher_head():
    p=run(["git","rev-parse","HEAD"],20)
    return p.stdout.strip() if p.returncode==0 else ""

def update_repo():
    log("G0 git fetch origin main")
    p=run(["git","fetch","origin","main"],90)
    if p.returncode!=0: raise RuntimeError("git fetch: "+(p.stderr or p.stdout))
    local=watcher_head()
    remote=run(["git","rev-parse","origin/main"],20).stdout.strip()
    if local!=remote:
        log("G1 fast-forward "+local[:8]+" -> "+remote[:8])
        p=run(["git","merge","--ff-only","origin/main"],60)
        if p.returncode!=0: raise RuntimeError("git merge: "+(p.stderr or p.stdout))
    else:
        log("G1 repo already current "+local[:8])

def restart_watcher():
    log("G2 restart watcher targeted")
    if os.name=="nt":
        ps=r"""Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'bazor_github_watcher\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"""
        run(["powershell","-NoProfile","-Command",ps],20)
    flags=(getattr(subprocess,"CREATE_NO_WINDOW",0)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)) if os.name=="nt" else 0
    wlog=(ROOT/"pc-relay"/"BAZOR_DATA"/"watcher.log")
    wlog.parent.mkdir(parents=True,exist_ok=True)
    h=wlog.open("a",encoding="utf-8",buffering=1)
    subprocess.Popen([sys.executable,str(WATCHER)],cwd=str(WATCHER.parent),stdout=h,stderr=subprocess.STDOUT,creationflags=flags)

def trigger_auto():
    ROOM.mkdir(parents=True,exist_ok=True)
    try:data=json.loads(CONTROL.read_text(encoding="utf-8")) if CONTROL.exists() else {}
    except Exception:data={}
    data["request_seq"]=int(data.get("request_seq") or 0)+1
    data["request_action"]="angry"
    data["go_requested"]=True
    data["auto_mode"]=True
    data["angry_mode"]=True
    data["priority"]="MAX_AUTOMATION"
    data["request_at"]=time.strftime("%Y-%m-%dT%H:%M:%S")
    CONTROL.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    log("G3 AUTO TOTAL injected request_seq="+str(data["request_seq"]))

def wait_ready(limit=180):
    log("G4 waiting for V3 beta/control")
    deadline=time.time()+limit
    ports=(8768,8769,8780,8765)
    while time.time()<deadline:
        try:
            if CONTROL.exists():
                d=json.loads(CONTROL.read_text(encoding="utf-8"))
                if d.get("beta_ready") and d.get("control_url"):
                    log("G5 READY "+d["control_url"])
                    return d
        except Exception:pass
        for port in ports:
            st,body=http(port,"/api/control/status",1.5)
            if st==200:
                try:
                    d=json.loads(body).get("control") or {}
                    if d.get("beta_ready"):
                        log("G5 READY http://127.0.0.1:"+str(port)+"/control")
                        return d
                except Exception:pass
        time.sleep(2)
    raise RuntimeError("timeout: V3 beta not ready after 180s")

def open_control(data):
    url=data.get("control_url") or data.get("beta_url") or "http://127.0.0.1:8768/control"
    log("G6 open "+url)
    if os.name=="nt": os.startfile(url)  # local, predefined URL only

def main():
    log("=== BAZOR ROOM V3 ONESHOT RECOVERY ===")
    try:
        update_repo()
        restart_watcher()
        time.sleep(3)
        trigger_auto()
        data=wait_ready()
        open_control(data)
        log("G7 OK V3 BETA READY")
        return 0
    except Exception as e:
        log("BLOCKED "+type(e).__name__+": "+str(e))
        try:
            diag=ROOM/"diagnostics"
            diag.mkdir(parents=True,exist_ok=True)
            (diag/"oneshot_failure.txt").write_text(LOG.read_text(encoding="utf-8"),encoding="utf-8")
        except Exception:pass
        return 2

if __name__=="__main__":
    raise SystemExit(main())
