import json, subprocess, time, urllib.request, os

REPO="VincBZH/bazor-mobile"
CORE="http://127.0.0.1:8775/api/v1/chat"
POLL=10
MARK="[BAZOR-WATCHER-DONE]"
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
LAST_HEAD=None

def safe_update():
    global LAST_HEAD
    try:
        remote=gh(["api",f"repos/{REPO}/commits/main","--jq",".sha"]).strip()
        local=gh(["-C",ROOT,"rev-parse","HEAD"]).strip()
        if remote and remote != local:
            print("[UPDATE] Nouvelle version BAZOR detectee :",remote[:7])
            p=subprocess.run(["git","-C",ROOT,"pull","--ff-only"],capture_output=True,text=True,encoding="utf-8",errors="replace")
            if p.returncode:
                print("[BLOQUE UPDATE]",p.stderr.strip() or p.stdout.strip())
            else:
                print("[OK UPDATE] BAZOR mis a jour :",remote[:7])
                LAST_HEAD=remote
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
