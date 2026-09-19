from __future__ import annotations
import json, os, re, urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

VERSION="2.4.1"
ROOT=Path(__file__).resolve().parent
STATE=ROOT/"state.json"
PROJECTS=ROOT/"projects.json"
INCIDENTS=ROOT/"incidents"

HTML=r'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BAZOR AI ROOM</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;background:#07101d;color:#eaf4ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#10284b 0,#07101d 45%,#040912 100%);min-height:100vh}header{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:26px 30px;border-bottom:1px solid #1b416b;background:#07101ddd;position:sticky;top:0}h1{margin:0;font-size:24px}h1 span{font-size:13px;color:#72d0ff}header p{margin:5px 0 0;color:#91a9c7}.pill{border:1px solid #2c649b;border-radius:999px;padding:9px 13px}main{max-width:1160px;margin:22px auto;padding:0 18px 50px;display:grid;gap:16px}.panel{border:1px solid #1b416b;border-radius:18px;background:#0b1728ee;padding:18px;box-shadow:0 15px 35px #0005}.head{display:flex;justify-content:space-between;align-items:center;gap:14px}.head h2{margin:0 0 14px;font-size:18px}.eng{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card,.project{padding:15px;border:1px solid #1c3d65;border-radius:13px;background:#09182a}.ok{color:#77efa7}.bad{color:#ff8f8f}.unknown{color:#ffd67a}.progress{height:10px;border-radius:99px;background:#06101d;overflow:hidden;border:1px solid #17395f}.progress div{height:100%;background:linear-gradient(90deg,#35a7ff,#80e8ff);width:0}.router{display:grid;grid-template-columns:220px 180px 1fr;gap:10px}select,button{background:#0a213a;color:#eef7ff;border:1px solid #2a598b;border-radius:10px;padding:10px}button{background:#0d568b;font-weight:700;cursor:pointer}.result{border:1px dashed #2a598b;border-radius:10px;padding:10px}.projects{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.note{color:#9eb4ce}@media(max-width:800px){header{flex-direction:column;align-items:flex-start}.eng,.projects,.router{grid-template-columns:1fr}}
</style></head><body><header><div><h1>BAZOR AI ROOM <span>V2.4.1</span></h1><p>Vincent × BAZOR Core × GPT × Mammouth × Ollama</p></div><div id="state" class="pill">Démarrage…</div></header>
<main>
<section class="panel"><div class="head"><h2>Moteurs</h2><select id="mode"><option value="auto">AUTO BAZOR</option><option value="gpt">GPT</option><option value="mammouth">Mammouth</option><option value="ollama">Ollama</option></select></div><div class="eng"><div class="card"><b>GPT</b><div id="gpt">…</div><small>coordination / synthèse</small></div><div class="card"><b>Mammouth</b><div id="mammouth">…</div><small>complexité / secours</small></div><div class="card"><b>Ollama</b><div id="ollama">…</div><small>local / gratuit</small></div></div></section>
<section class="panel"><div class="head"><h2>Projet courant</h2><span id="pct">0%</span></div><div class="progress"><div id="bar"></div></div><div id="project" class="project"></div></section>
<section class="panel"><div class="head"><h2>Routeur</h2></div><div class="router"><select id="kind"><option value="simple">Simple</option><option value="local">Local</option><option value="architecture">Architecture</option><option value="synthesis">Synthèse</option><option value="complex">Complexe</option><option value="second_opinion">Deuxième avis</option></select><button id="go">Choisir le moteur</button><div id="route" class="result">—</div></div></section>
<section class="panel"><div class="head"><h2>Projets BAZOR</h2></div><div id="projects" class="projects"></div></section>
<section class="panel"><b>DEFAULT_RECOVERY actif</b><p class="note">Message incomplet, handoff absent, crash, timeout ou erreur répétée : incident horodaté, pas de DONE, fallback sûr.</p></section>
</main>
<script>
async function j(u,o){let r=await fetch(u,o);return r.json()}function c(v){return v===true?'ok':v===false?'bad':'unknown'}function l(v){return v===true?'● DISPONIBLE':v===false?'● INDISPONIBLE':'● À VÉRIFIER'}
async function refresh(){let s=await j('/api/status'),p=s.state?.project||{};state.textContent=(p.delivery_state||p.status||'BOOTSTRAP').toUpperCase();let n=Number(p.progress_percent||0);pct.textContent=n+'%';bar.style.width=n+'%';project.innerHTML='<b>'+(p.name||p.id||'BAZOR AI ROOM')+'</b><br>État : '+(p.delivery_state||p.status||'—')+'<br>Tâche : '+(p.current_task||'—')+'<br>Suite : '+(p.next_task||'—');for(let k of ['gpt','mammouth','ollama']){let e=s.engines?.[k]||{},el=document.getElementById(k);el.textContent=l(e.available);el.className=c(e.available)}let ps=await j('/api/projects');projects.innerHTML=(ps.projects||[]).map(x=>'<div class="card"><b>'+x.name+'</b><div>'+x.status+'</div><small>'+x.next_step+'</small></div>').join('')||'<div class="card">Aucun projet</div>'}
go.onclick=async()=>{let body={task_class:kind.value},m=mode.value;if(m!=='auto')body.manual=m;let r=await j('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});route.textContent=r.selected?'Moteur choisi : '+r.selected:'Aucun moteur prouvé disponible'};refresh().catch(e=>state.textContent='ERREUR UI');setInterval(()=>refresh().catch(()=>{}),10000)
</script></body></html>'''

REQUIRED=["message_id","timestamp_local","timestamp_utc","project_id","project_name","project_version","bazor_version","task_id","parent_task_id","source_agent","target_agent","status","progress_percent","summary","files","tests","errors","next_step","handoff_logic"]

def read_json(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def probe(url,timeout=1.5):
    if not url:return {"available":None,"reason":"not_configured"}
    try:
        with urllib.request.urlopen(url,timeout=timeout) as r:return {"available":200<=getattr(r,"status",500)<500,"status":getattr(r,"status",None)}
    except Exception as e:return {"available":False,"error":str(e)}

def engines():
    return {
      "ollama":probe(os.getenv("BAZOR_OLLAMA_HEALTH_URL","http://127.0.0.1:11434/api/tags")),
      "mammouth":probe(os.getenv("BAZOR_MAMMOUTH_HEALTH_URL","")),
      "gpt":{"available":None,"mode":os.getenv("BAZOR_GPT_MODE","relay"),"reason":"relay_status_not_configured"}
    }

def route(kind,manual=None):
    e=engines()
    if manual in {"gpt","mammouth","ollama"}:
        return {"mode":"manual","selected":manual if e[manual].get("available") is not False else None,"engines":e}
    if kind in {"simple","local"} and e["ollama"].get("available") is True:s="ollama"
    elif kind in {"architecture","synthesis","arbitration"} and e["gpt"].get("available") is True:s="gpt"
    elif kind in {"complex","second_opinion"} and e["mammouth"].get("available") is True:s="mammouth"
    elif e["gpt"].get("available") is True:s="gpt"
    elif e["mammouth"].get("available") is True:s="mammouth"
    elif e["ollama"].get("available") is True:s="ollama"
    else:s=None
    return {"mode":"auto","selected":s,"engines":e}

def incident(kind,message,extra=None):
    INCIDENTS.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc)
    data={"timestamp_utc":now.isoformat(),"version":VERSION,"type":kind,"message":message,"extra":extra or {}}
    p=INCIDENTS/(now.strftime("%Y%m%dT%H%M%SZ")+"_"+re.sub(r"[^A-Za-z0-9_-]+","_",kind)+".json")
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return str(p)

class H(BaseHTTPRequestHandler):
    server_version="BAZORRoom/2.4.1"
    def sendj(self,x,status=200):
        b=json.dumps(x,ensure_ascii=False,indent=2).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        p=self.path.split("?",1)[0]
        if p=="/":
            b=HTML.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=="/api/status":return self.sendj({"ok":True,"version":VERSION,"state":read_json(STATE,{}),"engines":engines()})
        if p=="/api/projects":return self.sendj(read_json(PROJECTS,{"projects":[]}))
        if p=="/health":return self.sendj({"ok":True,"version":VERSION})
        self.send_error(404)
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        try:data=json.loads(self.rfile.read(n).decode() if n else "{}")
        except Exception as e:
            ref=incident("invalid_json",str(e));return self.sendj({"ok":False,"error":"invalid_json","incident":ref},400)
        if self.path=="/api/route":return self.sendj({"ok":True,**route(str(data.get("task_class","simple")),data.get("manual"))})
        self.sendj({"ok":False,"error":"not_found"},404)
    def log_message(self,fmt,*args):print("[ROOM]",fmt%args)

def main():
    host=os.getenv("BAZOR_ROOM_HOST","127.0.0.1");port=int(os.getenv("BAZOR_ROOM_PORT","8765"))
    print(f"BAZOR AI ROOM {VERSION} -> http://{host}:{port}/")
    ThreadingHTTPServer((host,port),H).serve_forever()
if __name__=="__main__":main()
