from __future__ import annotations
import json, os, re, urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

VERSION="3.0.0-beta.2"
ROOT=Path(__file__).resolve().parent
STATE=ROOT/"state.json"
PROJECTS=ROOT/"projects.json"
INCIDENTS=ROOT/"incidents"
CONTEXT=ROOT/"context"
IDENTITIES=CONTEXT/"IDENTITIES.json"
CURRENT_STATE=CONTEXT/"CURRENT_STATE.json"
CONTEXT_INDEX=CONTEXT/"index.json"
CONTROL=ROOT/"control.json"

HTML=r'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BAZOR AI ROOM</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;background:#07101d;color:#eaf4ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#10284b 0,#07101d 45%,#040912 100%);min-height:100vh}header{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:26px 30px;border-bottom:1px solid #1b416b;background:#07101ddd;position:sticky;top:0}h1{margin:0;font-size:24px}h1 span{font-size:13px;color:#72d0ff}header p{margin:5px 0 0;color:#91a9c7}.pill{border:1px solid #2c649b;border-radius:999px;padding:9px 13px}main{max-width:1160px;margin:22px auto;padding:0 18px 50px;display:grid;gap:16px}.panel{border:1px solid #1b416b;border-radius:18px;background:#0b1728ee;padding:18px;box-shadow:0 15px 35px #0005}.head{display:flex;justify-content:space-between;align-items:center;gap:14px}.head h2{margin:0 0 14px;font-size:18px}.eng{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card,.project{padding:15px;border:1px solid #1c3d65;border-radius:13px;background:#09182a}.ok{color:#77efa7}.bad{color:#ff8f8f}.unknown{color:#ffd67a}.progress{height:10px;border-radius:99px;background:#06101d;overflow:hidden;border:1px solid #17395f}.progress div{height:100%;background:linear-gradient(90deg,#35a7ff,#80e8ff);width:0}.router{display:grid;grid-template-columns:220px 180px 1fr;gap:10px}select,button{background:#0a213a;color:#eef7ff;border:1px solid #2a598b;border-radius:10px;padding:10px}button{background:#0d568b;font-weight:700;cursor:pointer}.result{border:1px dashed #2a598b;border-radius:10px;padding:10px}.projects{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.note{color:#9eb4ce}@media(max-width:800px){header{flex-direction:column;align-items:flex-start}.eng,.projects,.router{grid-template-columns:1fr}}
</style></head><body><header><div><h1>BAZOR AI ROOM <span>V3 BETA</span></h1><p>Vincent × BAZOR Core × GPT × Mammouth × Ollama</p></div><div id="state" class="pill">Démarrage…</div></header>
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

CONTROL_HTML=r'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BAZOR AI ROOM V3 — CONTROL</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;background:#050910;color:#edf6ff}*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#07111f,#03070d);min-height:100vh}.wrap{max-width:1080px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:16px;align-items:center}.title{font-size:28px;font-weight:900}.sub{color:#8fa8c4;margin-top:5px}.badge{padding:11px 15px;border-radius:999px;border:1px solid #315d8d;font-weight:900}.ok{color:#76f1a5}.wait{color:#ffd56c}.bad{color:#ff8383}.run{color:#71c8ff}.hero{margin-top:18px;padding:20px;border:1px solid #244d79;border-radius:18px;background:#0a1627}.heroStatus{font-size:34px;font-weight:1000}.heroSub{margin-top:6px;color:#9eb5cf}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}.card{background:#091522;border:1px solid #1d4066;border-radius:15px;padding:15px}.label{font-size:11px;color:#89a2be;text-transform:uppercase;letter-spacing:.08em}.value{font-size:18px;font-weight:800;margin-top:6px;word-break:break-word}.buttons{display:grid;grid-template-columns:2fr 2fr 1fr 1fr;gap:12px;margin-top:16px}button{border:0;border-radius:14px;padding:17px 12px;font-weight:900;font-size:16px;cursor:pointer}.go{background:#116fbd;color:white}.auto{background:#a12635;color:white}.secondary{background:#18304b;color:#eef7ff}.stop{background:#4b2730;color:#ffdfe5}.timeline{margin-top:16px;background:#08111d;border:1px solid #1d3d61;border-radius:16px;padding:15px}.gate{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid #112941}.gate:last-child{border:0}.dot{font-size:16px}.small{font-size:12px;color:#839ab4}.airow{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.ai{padding:12px;border-radius:12px;background:#07111d;border:1px solid #183b61}.ai b{display:block}.tech{margin-top:14px}.tech summary{cursor:pointer;color:#9db5d0}.log{white-space:pre-wrap;background:#03070d;border:1px solid #193c61;border-radius:12px;padding:12px;margin-top:9px;max-height:360px;overflow:auto;color:#cce7ff}@media(max-width:800px){.grid,.airow,.buttons{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}.heroStatus{font-size:28px}}</style></head>
<body><div class="wrap">
<div class="top"><div><div class="title">BAZOR AI ROOM <span style="font-size:13px;color:#76cfff">V3 BETA CONTROL</span></div><div class="sub">Voir immédiatement si ça travaille vraiment, qui travaille, sur quoi, et avec quelle preuve.</div></div><div id="live" class="badge wait">CHARGEMENT…</div></div>

<div class="hero"><div class="label">ÉTAT RÉEL</div><div id="heroStatus" class="heroStatus">—</div><div id="heroSub" class="heroSub">—</div></div>

<div class="grid">
<div class="card"><div class="label">Tâche en cours</div><div id="task" class="value">—</div></div>
<div class="card"><div class="label">Étape / porte</div><div id="gate" class="value">—</div></div>
<div class="card"><div class="label">Suite automatique</div><div id="next" class="value">—</div></div>
<div class="card"><div class="label">Dernier moteur</div><div id="engine" class="value">—</div></div>
<div class="card"><div class="label">Dernier résultat</div><div id="result" class="value">—</div></div>
<div class="card"><div class="label">Dernière preuve</div><div id="proof" class="value">—</div></div>
</div>

<div class="airow">
<div class="ai"><b>GPT</b><span id="gpt">À vérifier</span></div>
<div class="ai"><b>Mammouth</b><span id="mammouth">À vérifier</span></div>
<div class="ai"><b>Ollama</b><span id="ollama">À vérifier</span></div>
</div>

<div class="buttons">
<button class="go" onclick="send('go')">▶ GO — 1 ÉTAPE MAINTENANT</button>
<button class="auto" onclick="send('angry')">😡 AUTO TOTAL — JUSQU'AU BOUT</button>
<button class="secondary" onclick="send('export_logs')">📦 LOGS</button>
<button class="secondary" onclick="send('screenshot')">📸 CAPTURE</button>
<button class="stop" onclick="send('stop_auto')">■ STOP AUTO</button>
</div>

<div class="timeline"><div class="label">GRAFCET / progression réelle</div><div id="timeline"></div></div>
<details class="tech"><summary>Détails techniques</summary><div id="log" class="log">—</div></details>
</div>
<script>
async function api(u,o){let r=await fetch(u,o);let t=await r.text();try{return JSON.parse(t)}catch(e){return {ok:false,error:t}}}
function esc(v){return String(v??'—')}
function setAi(id,v){let el=document.getElementById(id),a=v?.available;if(a===true){el.textContent='DISPONIBLE';el.className='ok'}else if(a===false){el.textContent='INDISPONIBLE';el.className='bad'}else{el.textContent='À VÉRIFIER';el.className='wait'}}
async function refresh(){
 let [s,st]=await Promise.all([api('/api/control/status'),api('/api/status')]);let c=s.control||{},now=Math.floor(Date.now()/1000),seen=Number(c.watcher_last_seen_epoch||0),age=seen?now-seen:999999;
 let busy=!!c.working, fresh=age<25, blocked=c.last_result_status==='BLOCKED';
 live.textContent=busy?'● TRAVAIL EN COURS':(fresh?'● WATCHER ACTIF':'● WATCHER SANS PREUVE');
 live.className='badge '+(busy?'run':(fresh?'ok':'bad'));
 heroStatus.textContent=busy?'ÇA BOSSE VRAIMENT':(blocked?'BLOQUÉ — DIAGNOSTIC DISPONIBLE':(c.auto_mode?'AUTO TOTAL ACTIF':'EN ATTENTE'));
 heroStatus.className='heroStatus '+(busy?'run':(blocked?'bad':(c.auto_mode?'ok':'wait')));
 heroSub.textContent=busy?('Exécution '+esc(c.current_task||c.last_task)+' • '+esc(c.last_action)):(fresh?(age+' s depuis le dernier heartbeat'):'Aucun heartbeat récent');
 task.textContent=esc(c.current_task||c.last_task);gate.textContent=esc(c.current_gate);next.textContent=esc(c.next_task||'calcul en cours');
 engine.textContent=esc((c.last_engine||'—')+(c.last_model?' / '+c.last_model:''));
 result.textContent=esc(c.last_result_status||'—');result.className='value '+(blocked?'bad':((c.last_result_status==='VERIFIE'||c.last_result_status==='V3_BETA_READY')?'ok':'wait'));
 proof.textContent=esc(c.last_proof||'—');
 setAi('gpt',st.engines?.gpt);setAi('mammouth',st.engines?.mammouth);setAi('ollama',st.engines?.ollama);
 let gs=c.grafcet||[];timeline.innerHTML=gs.map(x=>'<div class="gate"><span class="dot '+(x.ok?'ok':'bad')+'">●</span><div><b>'+esc(x.gate)+'</b><div class="small">'+esc(x.detail)+'</div></div></div>').join('')||'<div class="small">Aucune porte exécutée.</div>';
 log.textContent=JSON.stringify(c,null,2);
}
async function send(action){await api('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});await refresh()}
refresh();setInterval(refresh,1500);
</script></body></html>'''

REQUIRED=["message_id","timestamp_local","timestamp_utc","project_id","project_name","project_version","bazor_version","task_id","parent_task_id","source_agent","target_agent","status","progress_percent","summary","files","tests","errors","next_step","handoff_logic"]

def read_json(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def bootstrap_status():
    identities=read_json(IDENTITIES,{})
    current=read_json(CURRENT_STATE,{})
    index=read_json(CONTEXT_INDEX,{})
    agents=(identities.get("agents") or {}) if isinstance(identities,dict) else {}
    required_agents={"gpt","ollama","mammouth","bazor_core"}
    identities_ok=required_agents.issubset(set(agents.keys()))
    provenance_ok=isinstance(index,dict) and bool(index.get("required_provenance"))
    return {
      "identities_loaded":identities_ok,
      "current_state_loaded":bool(current),
      "memory_index_loaded":bool(index),
      "provenance_schema_loaded":provenance_ok,
      "ready_for_chat":bool(identities_ok and current and provenance_ok),
      "agent_ids":sorted(agents.keys()),
      "protected_categories":index.get("protected_categories",[]) if isinstance(index,dict) else []
    }

def control_state():
    data=read_json(CONTROL,{})
    if not isinstance(data,dict): data={}
    data.setdefault("request_seq",0)
    data.setdefault("processed_seq",0)
    data.setdefault("auto_mode",False)
    data.setdefault("angry_mode",False)
    data.setdefault("working",False)
    return data

def control_request(action):
    action=str(action or "").strip().lower()
    if action not in {"go","angry","export_logs","screenshot","stop_auto"}:
        return {"ok":False,"error":"invalid_control_action"}
    data=control_state()
    data["request_seq"]=int(data.get("request_seq") or 0)+1
    data["request_action"]=action
    data["request_at"]=datetime.now(timezone.utc).isoformat()
    data["go_requested"]=True
    if action=="angry":
        data["angry_mode"]=True
        data["auto_mode"]=True
        data["priority"]="MAX_AUTOMATION"
    CONTROL.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"ok":True,"control":data}

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
    server_version="BAZORRoom/2.4.2"
    def sendj(self,x,status=200):
        b=json.dumps(x,ensure_ascii=False,indent=2).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        p=self.path.split("?",1)[0]
        if p=="/":
            b=HTML.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=="/control":
            b=CONTROL_HTML.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=="/api/status":return self.sendj({"ok":True,"version":VERSION,"state":read_json(STATE,{}),"engines":engines(),"bootstrap":bootstrap_status()})
        if p=="/api/context":return self.sendj({"ok":True,"bootstrap":bootstrap_status(),"current_state":read_json(CURRENT_STATE,{})})
        if p=="/api/control/status":return self.sendj({"ok":True,"control":control_state()})
        if p=="/api/projects":return self.sendj(read_json(PROJECTS,{"projects":[]}))
        if p=="/app.js":
            b=b"// BAZOR AI ROOM 2.4.2 - UI JavaScript is embedded in / for standalone reliability.\n";self.send_response(200);self.send_header("Content-Type","application/javascript; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=="/style.css":
            b=b"/* BAZOR AI ROOM 2.4.2 - UI CSS is embedded in / for standalone reliability. */\n";self.send_response(200);self.send_header("Content-Type","text/css; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=="/health":return self.sendj({"ok":True,"version":VERSION})
        self.send_error(404)
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        try:data=json.loads(self.rfile.read(n).decode() if n else "{}")
        except Exception as e:
            ref=incident("invalid_json",str(e));return self.sendj({"ok":False,"error":"invalid_json","incident":ref},400)
        if self.path=="/api/route":return self.sendj({"ok":True,**route(str(data.get("task_class","simple")),data.get("manual"))})
        if self.path=="/api/control":
            result=control_request(data.get("action"));return self.sendj(result,200 if result.get("ok") else 400)
        self.sendj({"ok":False,"error":"not_found"},404)
    def log_message(self,fmt,*args):print("[ROOM]",fmt%args)

def main():
    host=os.getenv("BAZOR_ROOM_HOST","127.0.0.1");port=int(os.getenv("BAZOR_ROOM_PORT","8765"))
    print(f"BAZOR AI ROOM {VERSION} -> http://{host}:{port}/")
    ThreadingHTTPServer((host,port),H).serve_forever()
if __name__=="__main__":main()
