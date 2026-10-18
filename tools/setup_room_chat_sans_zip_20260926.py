# BAZOR AI ROOM : correctif sans ZIP, limité au chat Ollama local.
# Python standard library seulement ; n'exécute aucun ancien lanceur.
from __future__ import annotations
import hashlib, os, shutil, socket, sys
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get('LOCALAPPDATA', '.')) / 'BazorAIROOM'
APP = BASE / 'app.py'
EXPECTED = '48bc9d11b27e6442d2a1916209353e90b0d528935973d825bd506fd8c70a00df'

def must_replace(src, old, new):
    if src.count(old) != 1:
        raise RuntimeError('structure du programme inconnue: ' + old[:55])
    return src.replace(old, new, 1)

BACKEND = '''# BAZOR_CHAT_CORE_V1 - addon local sans fournisseur payant
import threading as _chat_threading
_CHAT_LOCK = _chat_threading.Lock()
_CHAT_HISTORY = ROOT / "chat_history.json"

def _chat_core_status():
    try:
        req=urllib.request.Request("http://127.0.0.1:8775/api/v1/health")
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=3) as r:
            x=json.loads(r.read(524288).decode("utf-8"))
        return {"core":x.get("ok") is True,"ollama":x.get("ollama",{}).get("online") is True}
    except Exception:
        return {"core":False,"ollama":False}

def _chat_history():
    if not _CHAT_HISTORY.exists(): return []
    if _CHAT_HISTORY.stat().st_size>2097152:raise ValueError("historique_trop_grand")
    v=json.loads(_CHAT_HISTORY.read_text(encoding="utf-8"))
    if not isinstance(v,list):raise ValueError("historique_invalide")
    return v[-40:]

def _chat_reply(data):
    msg=data.get("text") if isinstance(data,dict) else None
    if not isinstance(msg,str) or not msg.strip() or len(msg)>6000:
        return {"ok":False,"error":"Message vide ou trop long (6000 caractères max)"},400
    if not _CHAT_LOCK.acquire(blocking=False):
        return {"ok":False,"error":"Une demande est déjà en cours"},409
    try:
        if not all(_chat_core_status().values()):
            return {"ok":False,"error":"Core ou Ollama non disponible sur ce PC"},503
        try:hist=_chat_history()
        except Exception:return {"ok":False,"error":"Historique illisible. Aucun fichier modifié"},500
        ctx="\\n\\n".join("Vincent: "+str(h.get("text",""))[:400]+"\\nOllama: "+str(h.get("answer",""))[:600] for h in hist[-3:])
        prompt=("Contexte des échanges précédents:\\n"+ctx+"\\n\\nQuestion actuelle:\\n"+msg.strip()) if ctx else msg.strip()
        body=json.dumps({"text":prompt,"target":"ollama","model":"llama3.2:3b"},ensure_ascii=False).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8775/api/v1/chat",data=body,headers={"Content-Type":"application/json; charset=utf-8"},method="POST")
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=120) as r:
                result=json.loads(r.read(2097152).decode("utf-8"))
        except Exception as e:return {"ok":False,"error":"Core n'a pas répondu: "+type(e).__name__},502
        o=result.get("ollama") if isinstance(result,dict) else None
        if not isinstance(o,dict) or o.get("ok") is not True or not str(o.get("answer") or "").strip():
            return {"ok":False,"error":"Réponse Ollama non confirmée"},502
        item={"text":msg.strip(),"answer":o["answer"],"model":o.get("model","llama3.2:3b")}
        try:
            tmp=_CHAT_HISTORY.with_suffix(".json.tmp")
            tmp.write_text(json.dumps((hist+[item])[-40:],ensure_ascii=False,indent=2),encoding="utf-8")
            tmp.replace(_CHAT_HISTORY)
        except Exception:return {"ok":False,"error":"Réponse reçue, mais historique non enregistré"},500
        return {"ok":True,"answer":item["answer"],"model":item["model"]},200
    finally:_CHAT_LOCK.release()

'''
HTML = '''<section class="panel" id="bazorChat"><h2>Chat local — Ollama via Core</h2><p class="note" id="chatHealth">Connexion en cours...</p><div id="chatLog" style="background:#06101d;border:1px solid #285276;border-radius:10px;min-height:180px;max-height:340px;overflow:auto;padding:12px;white-space:pre-wrap;margin-bottom:10px">Écris ton premier message ci-dessous.</div><textarea id="chatText" rows="3" maxlength="6000" placeholder="Écris à Ollama..." style="width:100%;padding:12px;background:#071b2c;color:white;border:1px solid #3575a0;border-radius:10px"></textarea><button type="button" id="chatSend">Envoyer à Ollama (local)</button><span id="chatInfo" class="note"> Aucun appel payant</span></section>
'''
JS = '''// BAZOR_CHAT_CORE_V1
async function chatFetch(u,o){let r=await fetch(u,o);let x=await r.json();if(!r.ok)throw Error(x.error||String(r.status));return x}
async function chatRefresh(){try{let s=await chatFetch('/api/chat/core');chatHealth.textContent=s.core&&s.ollama?'Core + Ollama connectés':'Core ou Ollama indisponible';let h=await chatFetch('/api/chat/history');chatLog.replaceChildren();if(!h.history.length){chatLog.textContent='Conversation locale prête.';}for(let m of h.history){let d=document.createElement('div');d.style.marginBottom='12px';d.textContent='Vincent : '+m.text+'\\nOllama : '+m.answer;chatLog.appendChild(d);}chatLog.scrollTop=chatLog.scrollHeight;}catch(e){chatInfo.textContent=e.message}}
chatSend.onclick=async()=>{let v=chatText.value.trim();if(!v)return;chatSend.disabled=true;chatInfo.textContent='Ollama réfléchit...';try{let r=await chatFetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:v})});chatText.value='';await chatRefresh();chatInfo.textContent='Réponse réelle : '+r.model;}catch(e){chatInfo.textContent=e.message;}finally{chatSend.disabled=false;}};
chatRefresh();
'''

def main():
    if not APP.is_file():raise RuntimeError('AI Room absente: '+str(APP))
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(('127.0.0.1',8765))==0:
            print('[STOP] AI Room est encore ouverte. Dans sa fenêtre uniquement: Ctrl+C. Puis réexécuter cette commande. NE PAS fermer Core.')
            return 3
    raw=APP.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:
        raise RuntimeError('Version locale différente de celle fournie; rien modifié. Envoie le app.py actuel.')
    s=raw.decode('utf-8')
    s=must_replace(s,'VERSION="3.0.0-beta.3"','VERSION="3.1.0-beta.1"')
    s=must_replace(s,'<section class="panel"><div class="head"><h2>Projet courant</h2>',HTML+'<section class="panel"><div class="head"><h2>Projet courant</h2>')
    s=s.replace('</script></body></html>\'\'\'','\n'+JS+'</script></body></html>\'\'\'',1)
    s=must_replace(s,'class H(BaseHTTPRequestHandler):',BACKEND+'class H(BaseHTTPRequestHandler):')
    s=must_replace(s,'        if p=="/health":return self.sendj({"ok":True,"version":VERSION})','        if p=="/api/chat/core":return self.sendj(_chat_core_status())\n        if p=="/api/chat/history":\n            try:return self.sendj({"ok":True,"history":_chat_history()})\n            except Exception:return self.sendj({"ok":False,"error":"historique_invalide"},500)\n        if p=="/health":return self.sendj({"ok":True,"version":VERSION})')
    s=must_replace(s,'        if self.path=="/api/route":','        if self.path=="/api/chat":\n            result,status=_chat_reply(data)\n            return self.sendj(result,status)\n        if self.path=="/api/route":')
    s=must_replace(s,'"notrack":{"available":bool(os.getenv("NOTRACK_API_KEY"))','"notrack":{"available":None')
    compile(s,str(APP),'exec')
    backup=BASE/'Backups'/('AVANT_CHAT_SANS_ZIP_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(APP,backup/'app.py')
    candidate=BASE/'app.py.chat.new'
    candidate.write_text(s,encoding='utf-8')
    candidate.replace(APP)
    launcher=BASE/'DEMARRER_BAZOR_AI_ROOM.cmd'
    launcher.write_text('@echo off\r\ntitle BAZOR AI ROOM\r\npowershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue) { exit 3 } else { exit 0 }" >nul 2>&1\r\nif errorlevel 3 (echo AI Room est deja ouverte. & pause & exit /b 0)\r\ncd /d "%~dp0"\r\npython -u "%~dp0app.py"\r\npause\r\n',encoding='utf-8')
    print('[OK] Chat local installé et app.py sauvegardé dans:',backup)
    print('[SUITE] Dans cette fenêtre, lance : python -u "%LOCALAPPDATA%\\BazorAIROOM\\app.py"')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:print('[BLOQUE]',e);sys.exit(1)
