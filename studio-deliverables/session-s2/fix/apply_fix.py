"""Apply reviewed, fail-closed transformations; preserve local installation."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
MARK='BAZOR_SESSION_S2'

def replace(text, old, new, count=1):
    found=text.count(old)
    if found!=count:
        raise ValueError('Version locale non reconnue : signature absente ou ambiguë ('+old[:75]+'). Aucun remplacement aveugle.')
    return text.replace(old,new)

def js_function(text,name,new=None,transform=None):
    pattern=re.compile(r'^(?:async )?function '+re.escape(name)+r'\([^\n]*$',re.M)
    matches=list(pattern.finditer(text))
    if not matches:raise ValueError('Fonction JavaScript non reconnue : '+name)
    original=matches[-1].group()
    replacement=new if new is not None else transform(original)
    for match in reversed(matches):
        text=text[:match.start()]+(replacement if match==matches[-1] else '')+text[match.end():]
    return text

def transform_js(text):
    if MARK in text:return text
    text=replace(text,"asset_id:asset?.id||null","asset_id:['i2i','i2v','v2v'].includes(mode)?(asset?.id||null):null")
    text=js_function(text,'saveDraft',new="function saveDraft(){try{localStorage.removeItem('studio2-draft')}catch{}}")
    text=js_function(text,'selectedDone',new="function selectedDone(){return jobs.find(j=>j.id===selectedResult&&j.status==='done'&&j.outputs?.length)}")
    text=js_function(text,'buttons',transform=lambda s:s.replace("||jobs.some(j=>j.status==='done'&&j.outputs?.length)",''))
    text=js_function(text,'renderResult',transform=lambda s:s.replace("||jobs.find(j=>j.status==='done'&&j.outputs?.length)",'').replace("if(!j){","if(!j){clearAnalysisS2();",1).replace("resultSignature=signature;","resultSignature=signature;clearAnalysisS2();",1).replace("!autoAnalyzedJobs.has(j.id)","!autoAnalyzedJobs.has(j.id)&&sessionJobsS2.has(j.id)").replace("setTimeout(()=>runCorrections(outputIndex),0)","setTimeout(()=>{if(selectedResult===j.id)runCorrections(outputIndex)},0)"))
    text=js_function(text,'renderActivity',transform=lambda s:s.replace('function renderActivity(){','function renderActivity(){const visibleJobs=jobs.filter(j=>j.created>=sessionStartedS2||!terminal(j));').replace('const active=jobs.filter','const active=visibleJobs.filter').replace('||jobs[0]','||visibleJobs[0]').replace('=jobs.slice','=visibleJobs.slice'))
    text=js_function(text,'updateMode',transform=lambda s:s.replace('mode=m;',"if(['t2i','t2v'].includes(m))clearSourceS2();mode=m;",1))
    text=js_function(text,'upload',transform=lambda s:s.replace('if(!file||uploading)return;',"if(!file||uploading)return;if(['t2i','t2v'].includes(mode)){error('Choisis un mode avec image pour importer une référence.');return}",1))
    text=js_function(text,'reuse',transform=lambda s:s.replace('asset=p.asset_id?',"asset=['i2i','i2v','v2v'].includes(mode)&&p.asset_id?"))
    text=js_function(text,'generate',transform=lambda s:s.replace('selectedResult=j.id;',"sessionJobsS2.add(j.id);selectedResult=j.id;clearAnalysisS2();",1))
    text=replace(text,"$('uploadArea').classList.toggle('hidden',mode==='t2i')","$('uploadArea').classList.toggle('hidden',mode==='t2i'||mode==='t2v')")
    text=replace(text,"if(checkpoints.includes(ck))$('checkpoint').value=ck;","if(checkpoints.includes(ck))$('checkpoint').value=ck;else{const choice=generalCheckpointS2(checkpoints);if(choice)$('checkpoint').value=choice;else{const option=document.createElement('option');option.value='';option.textContent='Choisir un modèle image installé';$('checkpoint').prepend(option);$('checkpoint').value=''}}")
    text=text.replace("t2v:'Créez une courte vidéo. Vous pouvez aussi ajouter une photo de départ.'","t2v:'Créez une courte vidéo depuis le texte seul. Pour une photo de départ, choisissez Image → Vidéo.'")
    text=text.replace(' · prêt pour créer`',' · moteur joignable · workflow vérifié à l’envoi`')
    text=js_function(text,'init',new="""async function init(){try{const config=await api('/api/config');if(config.version!=='3.0.5')throw Error('Version Studio incompatible avec le correctif S2.');token=config.token;window.__bazorToken=token;await flushDebugEvents();await refreshHealth();if(!formRestored){saveDraft();formRestored=true;newCreationS2('t2i');mountSessionS2()}updateSpecs();connect();await refreshJobs();buttons()}catch(e){$('connectionText').textContent=e.message;debugEvent('init.error',{error:debugText(e?.message||e)});setTimeout(init,3000)}}""")
    for name in ('analyzeResult','runCorrections','applyAnalysisCorrection'):
        text=js_function(text,name,new='')
    text=replace(text,"let token='',mode='t2v'","const sessionStartedS2=Date.now()/1000,sessionJobsS2=new Set();\nlet token='',mode='t2v'")
    text += '\n'+(HERE/'payload/session_ui.js').read_text(encoding='utf-8')
    # Block changing the correction target in the middle of a bounded loop.
    text += "\ndocument.addEventListener('click',e=>{if(correctionBusy&&e.target.closest('[data-result],[data-analyze],[data-reuse],[data-variant],[data-image-job],[data-mode]')){e.preventDefault();e.stopImmediatePropagation();$('analysisStatus').textContent='Arrête les corrections avant de changer de création.'}},true);\n"
    return text

def transform_workflows(text):
    if MARK in text:return text
    text=replace(text,"    if p['mode'] not in ('t2v','i2v','t2i','i2i','v2v'): raise ValueError('Mode inconnu.')", "    if p['mode'] not in ('t2v','i2v','t2i','i2i','v2v'): raise ValueError('Mode inconnu.')\n    # BAZOR_SESSION_S2: text routes never inherit any image source.\n    if p['mode'] in ('t2i','t2v'): p['asset_id']=None")
    text=replace(text,"    def n(cls,**inputs): return {'class_type':cls,'inputs':inputs}","    if p['mode'] in ('t2i','t2v'): image_name=None\n    def n(cls,**inputs): return {'class_type':cls,'inputs':inputs}")
    text=replace(text,"    graph = _api_graph(graph)\n    if not isinstance(graph, dict) or not graph:","    graph = _api_graph(graph)\n    if p['mode']=='t2v' and isinstance(graph,dict):\n        image_name=None\n        if any(isinstance(n,dict) and ('loadimage' in _node_class(n).lower().replace('_','') or 'loadvideo' in _node_class(n).lower().replace('_','')) for n in graph.values()):\n            raise ValueError('Workflow texte vers vidéo refusé : il contient une source image ou vidéo. Sélectionne un vrai workflow T2V.')\n    if not isinstance(graph, dict) or not graph:")
    return text

def transform_studio(text):
    if MARK in text:return text
    text=replace(text,"VERSION='3.0.5'","# BAZOR_SESSION_S2\nfrom studio_session_guard import normalize_analysis_image, select_vision_model, read_media_limited, engine_error_summary\nfrom studio_h3_inventory import resolve_h3_inventory\nVERSION='3.0.5'")
    text=replace(text,"        return result['graph'],profile","        resolved,changes=resolve_h3_inventory(result['graph'],info)\n        if changes:self.debug('h3.inventory_resolved',changes=changes)\n        return resolved,profile")
    text=replace(text,"                    raise EngineError(json.dumps(body,ensure_ascii=False)[:3000],r.status)","                    self.debug('engine.rejection_detail',path=path,target=target,body=body)\n                    raise EngineError(engine_error_summary(body),r.status)")
    text=replace(text,"        if o.get('media')!='video':return [raw]","        if o.get('media')!='video':return [await asyncio.to_thread(normalize_analysis_image,raw)]")
    text=replace(text,"            raw=await response.content.read(30*1024*1024+1)","            raw=await read_media_limited(response.content)")
    start=text.index("        model=model_name if model_name in names")
    end=text.index("        params=j.get('params',{})",start)
    text=text[:start]+"        model=await select_vision_model(self,model_name,names)\n"+text[end:]
    text=replace(text,"    async def analyze_job(self,key,model_name='',output_index=0):", "    async def analyze_job(self,key,model_name='',output_index=0):\n        if self.gpu_lock.locked():raise ValueError('Le moteur local est occupé. Attends sa libération.')\n        async with self.gpu_lock:\n            queue=await self.request('GET','/queue')\n            if queue.get('queue_running') or queue.get('queue_pending'):\n                raise ValueError('Attends la fin des générations avant l’analyse visuelle pour préserver la mémoire GPU.')\n            return await self._analyze_job_s2(key,model_name,output_index)\n\n    async def _analyze_job_s2(self,key,model_name='',output_index=0):")
    return text

def transform_controls(text):
    if 'BAZOR_H3_CONTROLS_S21' in text:return text
    tree=ast.parse(text)
    replacements={
        '_api_graph':"def _api_graph(graph):\n    return unwrap_graph(graph)\n",
        '_patch_common_video_controls':"def _patch_common_video_controls(graph, p, prefix, info=None):\n    return patch_controls(graph, p, prefix, info)\n"}
    lines=text.splitlines(keepends=True)
    for node in reversed(tree.body):
        if isinstance(node,ast.FunctionDef) and node.name in replacements:
            lines[node.lineno-1:node.end_lineno]=[replacements.pop(node.name)]
    if replacements:raise ValueError('Fonctions H3 non reconnues : aucun remplacement.')
    text=''.join(lines)
    text=replace(text,"def patch_h3_graph(graph, p, image_name=None, prefix='AI_Simple_Studio_2/creation'):","def patch_h3_graph(graph, p, image_name=None, prefix='AI_Simple_Studio_2/creation', info=None):")
    text=replace(text,'dimensions = _patch_common_video_controls(graph, p, prefix)','dimensions = _patch_common_video_controls(graph, p, prefix, info)')
    return text+'\n# BAZOR_H3_CONTROLS_S21\nfrom studio_h3_controls import unwrap_graph, patch_controls\n'

def preserve_converter(original, updated):
    if 'BAZOR_H3_WRAPPER_S22' in updated:return updated
    old=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name=='_api_graph')
    source=''.join(original.splitlines(keepends=True)[old.lineno-1:old.end_lineno])
    source=source.replace('def _api_graph(', 'def _api_graph_legacy_s22(',1).rstrip()+'\n'
    # Retain a previously installed UI/subgraph converter as fallback.
    wrapper="\n# BAZOR_H3_WRAPPER_S22\ndef _api_graph(graph):\n    try:\n        return unwrap_graph(graph)\n    except ValueError:\n        return unwrap_graph(_api_graph_legacy_s22(graph))\n"
    node=next(n for n in ast.parse(updated).body if isinstance(n,ast.FunctionDef) and n.name=='_api_graph')
    lines=updated.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=[source+wrapper]
    return ''.join(lines)

def transform_scene_workflows(text):
    if 'BAZOR_SCENE_S23' in text:return text
    text=replace(text,"base = _prompt_without_browser_suffix(p.get('prompt', ''))","base = p.get('prepared_prompt') or _prompt_without_browser_suffix(p.get('prompt', ''))")
    text=replace(text,"    return p\n","    return prompt_options(p,raw)\n")
    text=text.replace('show one adult subject head-to-toe','show every requested subject head-to-toe')
    text=text.replace('STRICT standing pose: one adult subject upright on both feet, full weight-bearing posture, legs and feet visible, natural vertical alignment, no sitting, kneeling, lying down or floating','For subjects requested standing: upright on both feet, stable weight-bearing posture and natural alignment. Keep other subjects in their requested poses and preserve their actions')
    text=text.replace("'seated, sitting, kneeling, lying down, crouching, floating, cut-off legs, cut-off feet, impossible balance'","'impossible balance, floating feet, cut-off legs, cut-off feet'")
    text=text.replace('stable framing, one clear action, no added subjects or objects','stable framing, preserve each requested action and subject, no unrequested subjects or objects')
    return text+'\n# BAZOR_SCENE_S23\nfrom studio_route_s23 import prompt_options\n'

def transform_scene_studio(text):
    if 'BAZOR_SCENE_S23' in text:return text
    tree=ast.parse(text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Studio')
    node=next(n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='graph_for')
    lines=text.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno]=['    async def graph_for(self,p,info,image_name,prefix):\n        return await graph_for_local(self,p,info,image_name,prefix)\n']
    text=''.join(lines)
    text=replace(text,"graph,_=await self.graph_for(p,info,image_name,prefix='AI_Simple_Studio_2/'+request_id)","graph,route=await self.graph_for(p,info,image_name,prefix='AI_Simple_Studio_2/'+request_id)")
    text=replace(text,"                self.save(j); self.prompt_library.remember_job(j)","                j['recipe']=recipe_for(p,graph,route)\n                self.save(j); self.prompt_library.remember_job(j)")
    text=replace(text,"workflows={m:bool(self.h3_workflow_candidates(m)) for m in ('t2v','i2v','v2v')}","workflows={m:('MiniMaxH3ImageToVideo' in info or bool(self.h3_workflow_candidates(m))) for m in ('t2v','i2v','v2v')}")
    text=text.replace('Target: ComfyUI Wan 2.2 5B,','Target: local ComfyUI, mode {p["mode"]},')
    text=text.replace('one concise English visual generation prompt','one faithful English visual generation prompt')
    text=text.replace('Preserve their intent and subjects. ','Preserve every requested subject, their counts, actions, objects, and spatial relationships. Put the requested actors and actions first, background last. Never replace a populated scene with an empty interior. ')
    text=text.replace("'num_ctx':2048,'num_predict':350","'num_ctx':4096,'num_predict':700")
    text=text.replace("'temperature':.5","'temperature':.2")
    text=replace(text,"    @routes.get('/api/workflow/{key}')", "    @routes.get('/api/recipe/{key}')\n    async def recipe(r):\n        key=r.match_info['key'];job=studio.store.get('job',key)\n        if not job:raise ValueError('Création introuvable.')\n        graph=studio.store.get('workflow',key)\n        if not graph:raise ValueError('Workflow de cette création non enregistré.')\n        value=job.get('recipe') or recipe_for(job['params'],graph,{'workflow':'historique enregistré'})\n        return web.json_response(value,headers={'Content-Disposition':'attachment; filename=creation_recipe.json'})\n\n    @routes.get('/api/workflow/{key}')")
    # Import before the CLI creates the app, not after web.run_app.
    return text.replace("VERSION='3.0.5'","# BAZOR_SCENE_S23\nfrom studio_route_s23 import graph_for_local, recipe_for\nVERSION='3.0.5'",1)

def transform_scene_js(text):
    if 'BAZOR_SCENE_S23' in text:return text
    text=js_function(text,'payload',transform=lambda s:s.replace('return{mode,','return{...preparedPayloadS23(),mode,'))
    text=replace(text,"  clearSourceS2(); selectedResult='';resultSignature='';pendingRequest=null;","  resetPreparedS23();clearSourceS2(); selectedResult='';resultSignature='';pendingRequest=null;")
    text=js_function(text,'reuse',transform=lambda s:s.replace("saveDraft();$('prompt').focus()","restorePreparedS23(p);saveDraft();$('prompt').focus()"))
    text=replace(text,"newCreationS2('t2i');mountSessionS2()","newCreationS2('t2i');mountSessionS2();mountSceneS23()")
    text=js_function(text,'optimize',new='')
    return text+'\n'+(HERE/'payload/scene_ui_s23.js').read_text(encoding='utf-8')

def prepare(root):
    files={}
    for name,fn in [('app/static/app.js',transform_js),('app/workflows.py',transform_workflows),('app/studio.py',transform_studio)]:
        files[name]=fn((root/name).read_text(encoding='utf-8-sig')).encode('utf-8')
    original=files['app/workflows.py'].decode()
    files['app/workflows.py']=preserve_converter(original,transform_controls(original)).encode()
    studio=files['app/studio.py'].decode()
    if 'BAZOR_SCENE_S23' not in studio and 'patch_h3_graph(raw,p,image_name,prefix,info=info)' not in studio:
        studio=replace(studio,'patch_h3_graph(raw,p,image_name,prefix)','patch_h3_graph(raw,p,image_name,prefix,info=info)')
    files['app/studio.py']=studio.encode()
    files['app/studio.py']=transform_scene_studio(files['app/studio.py'].decode()).encode()
    files['app/workflows.py']=transform_scene_workflows(files['app/workflows.py'].decode()).encode()
    files['app/static/app.js']=transform_scene_js(files['app/static/app.js'].decode()).encode()
    files['app/studio_route_s23.py']=(HERE/'payload/studio_route_s23.py').read_bytes()
    files['app/studio_h3_controls.py']=(HERE/'payload/studio_h3_controls.py').read_bytes()
    files['app/studio_session_guard.py']=(HERE/'payload/studio_session_guard.py').read_bytes()
    files['app/studio_h3_inventory.py']=(HERE/'payload/studio_h3_inventory.py').read_bytes()
    css=(root/'app/static/style.css').read_text(encoding='utf-8-sig')
    if MARK not in css:css+='\n/* BAZOR_SESSION_S2 */\n.session-s2{margin-bottom:24px;border-color:#2484a9}.s2-cards{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}.session-s2 .primary{background:#126b94}.workflow-dialog-s2{background:#101e31;color:#edf6ff;border:1px solid #3496bf;border-radius:18px;width:min(1100px,92vw);max-height:90vh;padding:24px}.workflow-dialog-s2::backdrop{background:#050b16cc}.workflow-scroll-s2{overflow:auto;max-height:65vh;margin:20px 0}.workflow-node-s2{fill:#172c45;stroke:#3eb8e2}.workflow-label-s2{fill:#eff9ff;font-size:13px}.workflow-port-s2{fill:#94c6df;font-size:11px}.workflow-edge-s2{fill:none;stroke:#5fc9dc;stroke-width:2}\n'
    files['app/static/style.css']=css.encode()
    html=(root/'app/static/index.html').read_text(encoding='utf-8-sig')
    html=html.replace('?v=3.0.5"','?v=3.0.5-s2"').replace('BAZOR AI Studio V3 · 3.0.5</span>','BAZOR AI Studio · 3.0.5 correctif S2</span>')
    html=html.replace('Moteur local · protégé','Moteur local').replace('Adapté à 8 Go','Mémoire à vérifier').replace('Point de départ · 8 Go','Point de départ').replace('correctif S2</span>','correctif S2.2</span>').replace('correctif S2.1</span>','correctif S2.2</span>')
    html=html.replace('correctif S2.2</span>','correctif S2.3</span>').replace('?v=3.0.5-s2"','?v=3.0.5-s23"')
    files['app/static/index.html']=html.encode()
    for name,data in files.items():
        if name.endswith('.py'):compile(data,name,'exec')
    release=json.loads((root/'release.json').read_text(encoding='utf-8-sig'))
    if release.get('version')!='3.0.5':raise ValueError('Ce correctif cible uniquement Studio 3.0.5.')
    for name,data in files.items():release['files'][name]=hashlib.sha256(data).hexdigest()
    release['build_id']='3.0.5-session-s2.3'
    files['release.json']=(json.dumps(release,ensure_ascii=False,indent=2)+'\n').encode()
    return files

def atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.s2-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as handle:handle.write(data);handle.flush();os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def install(root,dry_run=False):
    root=Path(root).resolve();files=prepare(root)
    changed={name:data for name,data in files.items() if not (root/name).is_file() or (root/name).read_bytes()!=data}
    if dry_run:return list(changed)
    if not changed:return {'status':'already_installed'}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=root/'backups'/('SESSION_S2_'+stamp);backup.mkdir(parents=True)
    audit=[];written=[]
    for name,data in changed.items():
        path=root/name;old=path.read_bytes() if path.exists() else None
        if old is not None:atomic_write(backup/name,old)
        audit.append({'what':name,'why':'Correctif session, routage et vision S2','who':'BAZOR installer S2','when':stamp,'before_sha256':hashlib.sha256(old).hexdigest() if old is not None else None,'after_sha256':hashlib.sha256(data).hexdigest()})
    atomic_write(backup/'manifest.json',json.dumps(audit,indent=2).encode())
    try:
        for name,data in changed.items():atomic_write(root/name,data);written.append(name)
    except BaseException:
        for name in reversed(written):
            old=backup/name
            if old.exists():atomic_write(root/name,old.read_bytes())
            else:(root/name).unlink(missing_ok=True)
        raise
    result={'status':'installed','backup':str(backup),'files':audit,'runtime_gpu_verified':False}
    atomic_write(root/'logs/session-s2-install.json',json.dumps(result,ensure_ascii=False,indent=2).encode())
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=r'C:\AI\SimpleStudioV2');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    print(json.dumps(install(args.root,args.check),ensure_ascii=False,indent=2))
