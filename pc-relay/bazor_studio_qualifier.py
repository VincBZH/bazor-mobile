import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "pc-relay" / "BAZOR_DATA" / "STUDIO_QUALIFICATION"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STUDIO = Path(r"C:\AI\SimpleStudioV2")
COMFY = Path(r"C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI")
ADB = Path(os.environ.get("LOCALAPPDATA", "")) / "BAZOR" / "Android" / "platform-tools" / "adb.exe"

EXPECTED_MODELS = [
    "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
    "qwen3vl_4b_int8_convrot.safetensors",
    "mmh3-4b-ClipProj-v3-mlp.safetensors",
]
BAD_MODEL_NAMES = [
    "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
]
TARGET_WORKFLOW = "MiniMax_H3_FL2V_8GB_VRAM.json"
TEXT_EXTS = {
    ".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".html",".htm",".css",
    ".json",".jsonl",".txt",".md",".ps1",".cmd",".bat",".yml",".yaml",
    ".ini",".cfg",".toml",".xml",".gradle",".properties"
}
PRUNE = {
    ".git","node_modules","models","checkpoints","output","outputs","temp","tmp",
    "cache","__pycache__",".venv","venv","downloads"
}

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def check(cid, name, ok, severity="P1", detail="", evidence=None):
    return {
        "id": cid, "name": name, "ok": bool(ok), "severity": severity,
        "detail": str(detail or ""), "evidence": evidence or {}
    }

def http_json(url, timeout=4):
    req = urllib.request.Request(url, headers={"User-Agent":"BAZOR-Studio-Qualifier/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        ctype = (r.headers.get("content-type") or "").lower()
        if "json" in ctype:
            return r.status, json.loads(raw.decode("utf-8", errors="replace"))
        return r.status, raw.decode("utf-8", errors="replace")

def http_post_json(url, payload, timeout=40):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type":"application/json","User-Agent":"BAZOR-Studio-Qualifier/1.0"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw=r.read().decode("utf-8",errors="replace")
        return r.status, json.loads(raw)

def walk_files(root, exts=None, max_files=6000, max_size=2_000_000):
    out=[]
    if not root.exists():
        return out
    for current, dirs, names in os.walk(root, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in PRUNE]
        for name in names:
            p=Path(current)/name
            if exts and p.suffix.lower() not in exts:
                continue
            try:
                if p.stat().st_size > max_size:
                    continue
            except Exception:
                continue
            out.append(p)
            if len(out) >= max_files:
                return out
    return out

def find_names(root, wanted):
    wanted_l={x.lower():x for x in wanted}
    found={x:[] for x in wanted}
    if not root.exists():
        return found
    for current, dirs, names in os.walk(root, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in {".git","output","outputs","temp","tmp","cache","__pycache__"}]
        for name in names:
            key=name.lower()
            if key in wanted_l:
                found[wanted_l[key]].append(str(Path(current)/name))
    return found

def search_text(root, needles, limit=120):
    results=[]
    needles_l=[n.lower() for n in needles]
    for p in walk_files(root, TEXT_EXTS, max_files=4000, max_size=1_500_000):
        try:
            text=p.read_text(encoding="utf-8",errors="replace")
        except Exception:
            continue
        low=text.lower()
        hits=[n for n,nl in zip(needles,needles_l) if nl in low]
        if hits:
            results.append({"path":str(p),"hits":hits})
            if len(results)>=limit:
                break
    return results

def compile_python(root):
    failures=[]
    checked=0
    for p in walk_files(root,{".py"},max_files=500,max_size=1_000_000):
        checked+=1
        try:
            src=p.read_text(encoding="utf-8",errors="replace")
            compile(src,str(p),"exec")
        except Exception as exc:
            failures.append({"path":str(p),"error":f"{type(exc).__name__}: {exc}"[:500]})
    return checked,failures

def parse_json_files(root):
    failures=[]
    checked=0
    for p in walk_files(root,{".json"},max_files=600,max_size=4_000_000):
        checked+=1
        try:
            json.loads(p.read_text(encoding="utf-8-sig",errors="strict"))
        except Exception as exc:
            failures.append({"path":str(p),"error":f"{type(exc).__name__}: {exc}"[:500]})
    return checked,failures

def check_js(root):
    node=shutil.which("node")
    if not node:
        return {"available":False,"checked":0,"failures":[]}
    failures=[]; checked=0
    for p in walk_files(root,{".js",".mjs",".cjs"},max_files=250,max_size=1_500_000):
        checked+=1
        try:
            cp=subprocess.run([node,"--check",str(p)],capture_output=True,text=True,timeout=12,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if cp.returncode!=0:
                failures.append({"path":str(p),"error":(cp.stderr or cp.stdout)[-1000:]})
        except Exception as exc:
            failures.append({"path":str(p),"error":f"{type(exc).__name__}: {exc}"[:500]})
    return {"available":True,"checked":checked,"failures":failures}

def check_ps(root):
    ps=shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return {"available":False,"checked":0,"failures":[]}
    failures=[]; checked=0
    for p in walk_files(root,{".ps1"},max_files=120,max_size=1_000_000):
        checked+=1
        escaped = str(p).replace("'", "''")
        script = (
            "$e=$null;$t=$null;"
            f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$t,[ref]$e)|Out-Null;"
            "if($e.Count -gt 0){$e|ForEach-Object{$_.Message};exit 2}"
        )
        try:
            cp=subprocess.run([ps,"-NoProfile","-Command",script],capture_output=True,text=True,timeout=15,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if cp.returncode!=0:
                failures.append({"path":str(p),"error":(cp.stderr or cp.stdout)[-1000:]})
        except Exception as exc:
            failures.append({"path":str(p),"error":f"{type(exc).__name__}: {exc}"[:500]})
    return {"available":True,"checked":checked,"failures":failures}

def port_open(port):
    s=socket.socket()
    s.settimeout(1.0)
    try:
        return s.connect_ex(("127.0.0.1",port))==0
    finally:
        s.close()

def process_snapshot():
    ps=shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return []
    script = r"""Get-CimInstance Win32_Process | Where-Object { ([string]$_.CommandLine) -match 'ComfyUI|SimpleStudio|Simple Studio|bazor' } | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Depth 3"""
    try:
        cp=subprocess.run([ps,"-NoProfile","-Command",script],capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if cp.returncode!=0 or not cp.stdout.strip():
            return []
        data=json.loads(cp.stdout)
        return data if isinstance(data,list) else [data]
    except Exception:
        return []

def listener_pids(port):
    ps=shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return []
    script=f"Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ConvertTo-Json"
    try:
        cp=subprocess.run([ps,"-NoProfile","-Command",script],capture_output=True,text=True,timeout=12,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        raw=cp.stdout.strip()
        if cp.returncode!=0 or not raw:
            return []
        data=json.loads(raw)
        if isinstance(data,list):
            return [int(x) for x in data]
        return [int(data)]
    except Exception:
        return []

def comfy_checks(results):
    for endpoint in ("/system_stats","/object_info","/queue"):
        url="http://127.0.0.1:8188"+endpoint
        try:
            status,data=http_json(url,timeout=6)
            results.append(check("COMFY"+endpoint.replace("/","_").upper(),f"ComfyUI {endpoint}",200<=status<300,"P0",f"HTTP {status}",{"type":type(data).__name__}))
        except Exception as exc:
            results.append(check("COMFY"+endpoint.replace("/","_").upper(),f"ComfyUI {endpoint}",False,"P0",f"{type(exc).__name__}: {exc}"))

def studio_http_checks(results):
    root_ok=False
    try:
        status,body=http_json("http://127.0.0.1:8191/",timeout=6)
        root_ok=200<=status<500
        results.append(check("STUDIO_HTTP_ROOT","Studio HTTP /",root_ok,"P0",f"HTTP {status}",{"preview":str(body)[:300]}))
    except Exception as exc:
        results.append(check("STUDIO_HTTP_ROOT","Studio HTTP /",False,"P0",f"{type(exc).__name__}: {exc}"))
    for ep in ("/health","/api/health","/status","/api/status"):
        try:
            status,body=http_json("http://127.0.0.1:8191"+ep,timeout=3)
            results.append(check("STUDIO_HTTP_"+ep.strip("/").replace("/","_").upper(),f"Studio {ep}",True,"P2",f"Endpoint facultatif HTTP {status}",{"preview":str(body)[:180],"optional":True}))
        except urllib.error.HTTPError as exc:
            results.append(check("STUDIO_HTTP_"+ep.strip("/").replace("/","_").upper(),f"Studio {ep}",True,"P2",f"Endpoint facultatif non exposé (HTTP {exc.code})",{"optional":True}))
        except Exception as exc:
            results.append(check("STUDIO_HTTP_"+ep.strip("/").replace("/","_").upper(),f"Studio {ep}",True,"P2",f"Endpoint facultatif indisponible: {type(exc).__name__}: {exc}",{"optional":True}))

def ui_feature_checks(results):
    tokens={
        "UI_PRESET_REALISTE":["réaliste","realiste"],
        "UI_PRESET_PHOTO":["photo"],
        "UI_PRESET_NB":["noir & blanc","noir et blanc","n&b"],
        "UI_PRESET_CORPS":["corps entier","full body"],
        "UI_GALLERY":["galerie","gallery"],
        "UI_HIDE":["masquer","hide"],
        "UI_DELETE":["supprimer","delete"],
        "UI_RECOVER":["récupérer","restaurer","recover","restore"],
        "UI_DIAG":["diag","diagnostic"],
        "UI_AUTOCORR":["correction","auto-correction","autocorrection"],
    }
    corpus=[]
    for p in walk_files(STUDIO,TEXT_EXTS,max_files=1200,max_size=1_000_000):
        try:
            corpus.append(p.read_text(encoding="utf-8",errors="replace").lower())
        except Exception:
            pass
    joined="\n".join(corpus)
    for cid,alts in tokens.items():
        ok=any(x in joined for x in alts)
        results.append(check(cid,cid.replace("_"," "),ok,"P1" if cid not in ("UI_PRESET_NB","UI_PRESET_CORPS") else "P2","Présent dans le code/config" if ok else "Chaîne/option non détectée dans les fichiers Studio"))

    duration_hits=search_text(STUDIO,["max=10","max=\"10\"","max: 10","<= 10","Math.min(10","min(10"],limit=30)
    results.append(check("UI_DURATION_10S","Durée vidéo <= 10 s",bool(duration_hits),"P1","Garde-fou 10 s détecté" if duration_hits else "Aucun garde-fou 10 s détecté par analyse statique",{"hits":duration_hits[:8]}))

def mammouth_matrix(results):
    profiles=["qwen","gemini","claude","mistral"]
    for profile in profiles:
        payload={
            "project_id":"simple-studio",
            "subproject_name":"Qualification Mammouth "+profile,
            "task":"TEST DE QUALIFICATION UNIQUEMENT. Ne modifie rien. Réponds exactement sous la forme QUALIF_OK puis une courte phrase technique en français.",
            "current_progress":0,"repair":False,"previous":"",
            "provider":"mammouth","mammouth_profile":profile,"apply_actions":False
        }
        try:
            status,data=http_post_json("http://127.0.0.1:8775/api/v1/task",payload,timeout=75)
            ok=(status==200 and str(data.get("engine") or "").lower()=="mammouth" and bool(data.get("model")) and not data.get("error"))
            results.append(check("MAMMOUTH_"+profile.upper(),f"Mammouth {profile}",ok,"P1",f"HTTP {status} • engine={data.get('engine')} • model={data.get('model')} • error={data.get('error')}",{"summary":str(data.get("summary") or "")[:300],"answer":str(data.get("answer") or "")[:300],"status":data.get("status")}))
        except Exception as exc:
            results.append(check("MAMMOUTH_"+profile.upper(),f"Mammouth {profile}",False,"P1",f"{type(exc).__name__}: {exc}"))

def ollama_matrix(results):
    try:
        status,data=http_json("http://127.0.0.1:11434/api/tags",timeout=5)
        models=[x.get("name") for x in (data.get("models") or [])]
        results.append(check("OLLAMA_TAGS","Ollama /api/tags",status==200,"P1",f"{len(models)} modèle(s)",{"models":models}))
    except Exception as exc:
        results.append(check("OLLAMA_TAGS","Ollama /api/tags",False,"P1",f"{type(exc).__name__}: {exc}"))
        return
    expected=["mistral:latest","gemma3:4b","qwen2.5-coder:7b"]
    for model in expected:
        ok=any(x==model or str(x).startswith(model.split(":")[0]+":") for x in models)
        results.append(check("OLLAMA_"+re.sub(r'[^A-Z0-9]+','_',model.upper()),f"Ollama modèle {model}",ok,"P1","Installé" if ok else "Absent",{"models":models}))

def adb_checks(results):
    ok=ADB.exists()
    results.append(check("ADB_EXISTS","ADB BAZOR présent",ok,"P2",str(ADB)))
    if not ok:
        return
    try:
        cp=subprocess.run([str(ADB),"devices"],capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        devices=[line.split()[0] for line in cp.stdout.splitlines() if "\tdevice" in line]
        results.append(check("ADB_DEVICE","Téléphone ADB autorisé",bool(devices),"P2",f"{len(devices)} appareil(s)",{"devices":devices}))
    except Exception as exc:
        results.append(check("ADB_DEVICE","Téléphone ADB autorisé",False,"P2",f"{type(exc).__name__}: {exc}"))

def action_engine_selftest(results):
    try:
        sys.path.insert(0,str(ROOT/"pc-relay"))
        from bazor_action_engine import ActionEngine
        with tempfile.TemporaryDirectory(prefix="bazor_qual_") as td, tempfile.TemporaryDirectory(prefix="bazor_qual_data_") as dd:
            root=Path(td); data=Path(dd)
            p=root/"demo.py"; p.write_text("x = 1\n",encoding="utf-8")
            eng=ActionEngine(data)
            eng.roots["qual"]=root
            eng.project_aliases["qual-project"]=["qual"]
            act=[{"op":"replace","root":"qual","path":"demo.py","find":"x = 1","replace":"x = 2","expected_count":1}]
            out=eng.apply("qual-project",act,"qualification")
            ok=bool(out.get("ok") and out.get("applied") and (out.get("preflight") or {}).get("ok") and p.read_text(encoding="utf-8")=="x = 2\n")
            pf=out.get("preflight") or {}
            detail=str(out.get("error") or "OK")
            if not ok:
                detail += " • detail="+str(out.get("detail") or "")+" • git="+json.dumps(pf.get("git") or {},ensure_ascii=False)[:700]
            results.append(check("ACTION_ENGINE_SANDBOX","Action Engine préflight + écriture temp",ok,"P0",detail,{"preflight":pf,"tests":out.get("tests"),"full":out}))
    except Exception as exc:
        results.append(check("ACTION_ENGINE_SANDBOX","Action Engine préflight + écriture temp",False,"P0",f"{type(exc).__name__}: {exc}"))

def summarize(results):
    total=len(results); passed=sum(1 for x in results if x["ok"])
    p0=[x for x in results if x["severity"]=="P0" and not x["ok"]]
    p1=[x for x in results if x["severity"]=="P1" and not x["ok"]]
    p2=[x for x in results if x["severity"]=="P2" and not x["ok"]]
    return {
        "total":total,"passed":passed,"failed":total-passed,
        "percent":round((passed*100/total),1) if total else 0,
        "p0_failed":len(p0),"p1_failed":len(p1),"p2_failed":len(p2),
        "operational":len(p0)==0,
    }

def run_full():
    results=[]
    results.append(check("PATH_STUDIO","Dossier Studio",STUDIO.exists(),"P0",str(STUDIO)))
    results.append(check("PATH_COMFY","Dossier ComfyUI",COMFY.exists(),"P0",str(COMFY)))

    model_found=find_names(COMFY,EXPECTED_MODELS+BAD_MODEL_NAMES) if COMFY.exists() else {x:[] for x in EXPECTED_MODELS+BAD_MODEL_NAMES}
    for name in EXPECTED_MODELS:
        results.append(check("MODEL_"+re.sub(r'[^A-Z0-9]+','_',name.upper()),f"Modèle {name}",bool(model_found.get(name)),"P0",model_found.get(name,["Absent"])[0] if model_found.get(name) else "Absent",{"paths":model_found.get(name,[])}))
    for name in BAD_MODEL_NAMES:
        refs=search_text(STUDIO,[name],limit=60) if STUDIO.exists() else []
        detail="Aucune référence active détectée" if not refs else f"{len(refs)} référence(s) trouvée(s) • "+str(refs[0].get("path") or "")
        results.append(check("BADREF_"+re.sub(r'[^A-Z0-9]+','_',name.upper()),f"Ancienne référence {name} absente",not refs,"P0",detail,{"refs":refs[:20]}))

    wf_found=find_names(STUDIO,[TARGET_WORKFLOW]).get(TARGET_WORKFLOW,[]) if STUDIO.exists() else []
    if not wf_found and COMFY.exists():
        wf_found=find_names(COMFY,[TARGET_WORKFLOW]).get(TARGET_WORKFLOW,[])
    results.append(check("WORKFLOW_H3_EXISTS","Workflow MiniMax H3 8 Go présent",bool(wf_found),"P0",wf_found[0] if wf_found else "Absent",{"paths":wf_found}))
    if wf_found:
        try:
            wdata=json.loads(Path(wf_found[0]).read_text(encoding="utf-8-sig"))
            results.append(check("WORKFLOW_H3_JSON","Workflow H3 JSON valide",True,"P0","JSON valide",{"top_type":type(wdata).__name__}))
        except Exception as exc:
            results.append(check("WORKFLOW_H3_JSON","Workflow H3 JSON valide",False,"P0",f"{type(exc).__name__}: {exc}"))

    py_checked,py_fail=compile_python(STUDIO)
    results.append(check("SYNTAX_PYTHON","Syntaxe Python Studio",not py_fail,"P0",f"{py_checked} fichier(s), {len(py_fail)} échec(s)",{"failures":py_fail[:20]}))
    json_checked,json_fail=parse_json_files(STUDIO)
    results.append(check("SYNTAX_JSON","JSON Studio",not json_fail,"P0",f"{json_checked} fichier(s), {len(json_fail)} échec(s)",{"failures":json_fail[:20]}))
    js=check_js(STUDIO)
    results.append(check("SYNTAX_JS","Syntaxe JavaScript Studio",not js["failures"],"P1",f"node={js['available']} • {js['checked']} fichier(s) • {len(js['failures'])} échec(s)",js))
    ps=check_ps(STUDIO)
    results.append(check("SYNTAX_PS","Syntaxe PowerShell Studio",not ps["failures"],"P1",f"powershell={ps['available']} • {ps['checked']} fichier(s) • {len(ps['failures'])} échec(s)",ps))

    results.append(check("PORT_8188","Port ComfyUI 8188",port_open(8188),"P0","Ouvert" if port_open(8188) else "Fermé"))
    results.append(check("PORT_8191","Port Studio 8191",port_open(8191),"P0","Ouvert" if port_open(8191) else "Fermé"))
    comfy_checks(results)
    studio_http_checks(results)

    procs=process_snapshot()
    comfy_procs=[p for p in procs if "comfy" in str(p.get("CommandLine","")).lower()]
    studio_procs=[p for p in procs if "simplestudio" in str(p.get("CommandLine","")).lower() or "simple studio" in str(p.get("CommandLine","")).lower()]
    results.append(check("PROC_COMFY","Processus ComfyUI détecté",bool(comfy_procs),"P1",f"{len(comfy_procs)} processus apparent(s)",{"processes":comfy_procs[:10]}))
    results.append(check("PROC_STUDIO","Processus Studio détecté",bool(studio_procs),"P1",f"{len(studio_procs)} processus apparent(s)",{"processes":studio_procs[:10]}))
    owners8191=listener_pids(8191)
    results.append(check("PROC_STUDIO_SINGLE","Un seul serveur écoute Studio 8191",len(owners8191)==1,"P0",f"{len(owners8191)} PID(s) en écoute sur 8191: {owners8191}",{"listener_pids":owners8191,"processes":studio_procs[:10]}))

    ui_feature_checks(results)
    action_engine_selftest(results)
    ollama_matrix(results)
    mammouth_matrix(results)
    adb_checks(results)

    report={
        "version":"1.0","generated_at":now(),"studio":str(STUDIO),"comfy":str(COMFY),
        "summary":summarize(results),"results":results
    }
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime("%Y%m%d_%H%M%S")
    path=DATA_DIR/f"studio_qualification_{stamp}.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (DATA_DIR/"latest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report,path

def selftest():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"a.py").write_text("x=1\n",encoding="utf-8")
        (root/"good.json").write_text('{"a":1}',encoding="utf-8")
        (root/"bad.json").write_text('{"a":',encoding="utf-8")
        assert compile_python(root)[1]==[]
        checked,bad=parse_json_files(root)
        assert checked==2 and len(bad)==1
        hits=search_text(root,["x=1"])
        assert hits and hits[0]["path"].endswith("a.py")
    print("SELFTEST_OK")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--compact",action="store_true")
    args=ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    report,path=run_full()
    print(json.dumps({"summary":report["summary"],"report_file":str(path)},ensure_ascii=False))
    if args.compact:
        for x in report["results"]:
            if not x["ok"]:
                print(f"{x['severity']} FAIL {x['id']} :: {x['detail']}")
    return 0 if report["summary"]["p0_failed"]==0 else 2

if __name__=="__main__":
    raise SystemExit(main())
