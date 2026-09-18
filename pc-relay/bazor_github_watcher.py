import json, subprocess, time, urllib.request, os, sys

REPO="VincBZH/bazor-mobile"
CORE="http://127.0.0.1:8775/api/v1/chat"
CORE_HEALTH="http://127.0.0.1:8775/api/v1/security/status"
CORE_FAILS=0
PENDING_CORE_RESTART=False
POLL=10
MARK="[BAZOR-WATCHER-DONE]"
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
LAST_HEAD=None

def _git(*args):
    return subprocess.run(["git","-C",ROOT,*args],capture_output=True,text=True,encoding="utf-8",errors="replace")

def _restart_core():
    core_script=os.path.join(ROOT,"pc-relay","bazor_pc_relay_v3.py")
    try:
        if os.name=="nt":
            ps=r"""Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'bazor_pc_relay_v3\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"""
            subprocess.run(["powershell","-NoProfile","-Command",ps],capture_output=True,text=True,timeout=12)
            flags=getattr(subprocess,"CREATE_NEW_CONSOLE",0)
        else:
            flags=0
        env=os.environ.copy()
        env["BAZOR_MOBILE_PORT"]="8775"
        subprocess.Popen([sys.executable,core_script],cwd=os.path.dirname(core_script),env=env,creationflags=flags)
        print("[OK CORE RESTART] BAZOR Core 8775 relance avec la nouvelle version.")
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
        print(f"[CORE RESTART DIFFERE] {reason} - appairage actif/protege ({max(pairing,guard)} s).")
        return False
    PENDING_CORE_RESTART=False
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
            if any(x in changed for x in ("pc-relay/bazor_pc_relay_v3.py","pc-relay/mammouth_client.py","pc-relay/bazor_security.py")):
                maybe_restart_core("mise a jour de code")

            if "pc-relay/bazor_github_watcher.py" in changed:
                print("[SELF UPDATE] Rechargement du watcher avec la nouvelle version...")
                os.execv(sys.executable,[sys.executable,os.path.abspath(__file__)])
        else:
            LAST_HEAD=local
    except Exception as e:
        print("[BLOQUE UPDATE]",type(e).__name__,str(e))
def gh(args):
    p=subprocess.run(["gh"]+args,capture_output=True,text=True,encoding="utf-8",errors="replace")
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

print("=== BAZOR GITHUB WATCHER V1 ===")
print("Repo :",REPO)
print("Core :",CORE)
print("Polling : 10 s")
print("Aucun shell distant : seules les issues [bazor-queue] sont envoyees a /api/v1/chat.")
print()

while True:
    safe_update()
    ensure_core_alive()
    try:
        issues=json.loads(gh(["issue","list","--repo",REPO,"--state","open","--limit","30","--json","number,title,body"]))
        for issue in issues:
            if not issue["title"].lower().startswith("[bazor-queue]"): continue
            comments=gh(["issue","view",str(issue["number"]),"--repo",REPO,"--comments"])
            if MARK in comments: continue
            print(f"[QUEUE] #{issue['number']} {issue['title']}")
            prompt=(issue.get("body") or "").strip()
            result=core_chat(prompt)
            reply=MARK+"\n\n**BAZOR/Ollama — résultat**\n\n"+answer_text(result)
            gh(["issue","comment",str(issue["number"]),"--repo",REPO,"--body",reply])
            print(f"[OK] #{issue['number']} traite et retourne dans GitHub.")
    except Exception as e:
        print("[BLOQUE]",type(e).__name__,str(e))
    time.sleep(POLL)
