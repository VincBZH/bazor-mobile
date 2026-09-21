"""Local H3 topology and immutable per-job recipe. No remote/API video nodes."""
import copy
import hashlib
import json
import re

NATIVE = 'MiniMaxH3ImageToVideo'


def remote_nodes(graph, info=None):
    found=[]
    def walk(value):
        if isinstance(value,dict):
            kind=value.get('class_type') or value.get('type')
            if isinstance(kind,str):
                low=kind.lower()
                meta=(info or {}).get(kind,{})
                known=any(x in low for x in ('hailuo','seedance','kling')) or re.match(r'^(?:google)?veo|^(?:openai)?sora|^runway',low)
                if known or meta.get('api_node') or meta.get('is_api_node'):
                    found.append(kind)
            for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(graph)
    return sorted(set(found))


def schema(info, kind):
    value=info.get(kind,{}).get('input',{})
    return {**value.get('required',{}),**value.get('optional',{})}


def native_h3(p, info, image_name, prefix):
    from workflows import generation_prompt, generation_negative
    from studio_h3_inventory import resolve_h3_inventory
    def n(kind,**inputs):return {'class_type':kind,'inputs':inputs}
    # H3 always runs at 24 fps. Preserve requested seconds when another fps was chosen.
    target=max(5,round(p['frames']*24/p['fps']))
    frames=5+17*max(0,(target-5+16)//17)
    graph={
        'h3_model':n('UNETLoader',unet_name='minimax_h3_fl2va_pruned_int8_convrot.safetensors',weight_dtype='default'),
        'h3_clip':n('CLIPLoader',clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors',type='minimax'),
        'h3_vae':n('VAELoader',vae_name='minimax_h3_video_vae_fp16.safetensors'),
        'h3_condition':n(NATIVE,clip=['h3_clip',0],vae=['h3_vae',0],prompt=generation_prompt(p)+'\nAvoid: '+generation_negative(p),width=p['width'],height=p['height'],length=frames),
        'h3_noise':n('RandomNoise',noise_seed=p['seed']),
        'h3_guider':n('BasicGuider',model=['h3_model',0],conditioning=['h3_condition',0]),
        'h3_sampler':n('KSamplerSelect',sampler_name='res_multistep'),
        'h3_schedule':n('BasicScheduler',model=['h3_model',0],scheduler='simple',steps=p['steps'],denoise=1.0),
        'h3_sample':n('SamplerCustomAdvanced',noise=['h3_noise',0],guider=['h3_guider',0],sampler=['h3_sampler',0],sigmas=['h3_schedule',0],latent_image=['h3_condition',1]),
        'h3_decode':n('VAEDecode',samples=['h3_sample',0],vae=['h3_vae',0]),
        'h3_video':n('CreateVideo',images=['h3_decode',0],fps=24.0),
        'h3_save':n('SaveVideo',video=['h3_video',0],filename_prefix=prefix,format='auto',codec='auto'),
    }
    device=schema(info,'CLIPLoader').get('device',[])
    if device and isinstance(device[0],list):graph['h3_clip']['inputs']['device']='cpu' if 'cpu' in device[0] else 'default'
    if p['mode'] in ('i2v','v2v'):
        if not image_name:raise ValueError('La vidéo avec référence exige une image choisie.')
        graph['h3_image']=n('LoadImage',image=image_name)
        graph['h3_condition']['inputs']['first_frame']=['h3_image',0]
    elif p['mode']!='t2v':raise ValueError('H3 ne produit que des vidéos.')
    if p.get('tiled') and 'VAEDecodeTiled' in info:
        graph['h3_decode']=n('VAEDecodeTiled',samples=['h3_sample',0],vae=['h3_vae',0],tile_size=256,overlap=64,temporal_size=32,temporal_overlap=4)
    spec=schema(info,'SaveVideo').get('format',[])
    if spec and spec[0]=='COMFY_DYNAMICCOMBO_V3':
        graph['h3_save']['inputs'].pop('codec');graph['h3_save']['inputs']['format.codec']='auto'
    missing=sorted({n['class_type'] for n in graph.values()}-info.keys())
    if missing:raise ValueError('Vidéo H3 locale : nœuds manquants : '+', '.join(missing))
    graph,changes=resolve_h3_inventory(graph,info)
    # Check live contracts, including actual model lists, before any submission.
    for node in graph.values():
        kind=node['class_type'];fields=schema(info,kind)
        for key,value in node['inputs'].items():
            if key=='format.codec' and spec and spec[0]=='COMFY_DYNAMICCOMBO_V3':continue
            if key not in fields:raise ValueError('Contrat local incompatible : '+kind+'.'+key)
            options=fields[key][0] if fields[key] else None
            # Uploaded filenames can be newer than the cached /object_info list.
            if isinstance(options,list) and value not in options and not (kind=='LoadImage' and key=='image'):
                raise ValueError('Valeur locale non disponible : '+kind+'.'+key+' = '+str(value))
        required=info.get(kind,{}).get('input',{}).get('required',{})
        missing=set(required)-node['inputs'].keys()
        if missing:raise ValueError('Entrées locales manquantes : '+kind+' '+', '.join(sorted(missing)))
    return graph,{'family':'h3','label':'MiniMax H3 local','workflow':'native-h3-s23','frames_effective':frames,'fps_effective':24,'audio':False,'inventory_changes':changes,'negative_handling':'text_avoid_clause_no_negative_conditioning'}


async def graph_for_local(studio,p,info,image_name,prefix):
    from workflows import build,detect_profile,patch_h3_graph
    from studio_h3_inventory import resolve_h3_inventory
    if p['mode'] in ('t2i','i2i'):
        return build(p,info,image_name,prefix),{'family':'sd','label':'SDXL/SD','workflow':'native-sd'}
    profile=detect_profile(info)
    if profile['family']!='h3':return build(p,info,image_name,prefix),profile
    if NATIVE in info:return native_h3(p,info,image_name,prefix)
    failures=[]
    for path in studio.h3_workflow_candidates(p['mode'])[:20]:
        try:
            raw=json.loads(path.read_text(encoding='utf-8-sig'))
            remote=remote_nodes(raw,info)
            if remote:raise ValueError('workflow en ligne exclu : '+', '.join(remote))
            if isinstance(raw,dict) and isinstance(raw.get('nodes'),list):
                raw=await studio.request('POST','/workflow/convert',raw,timeout=60)
            remote=remote_nodes(raw,info)
            if remote:raise ValueError('workflow en ligne exclu : '+', '.join(remote))
            result=patch_h3_graph(raw,p,image_name,prefix,info=info)
            graph,changes=resolve_h3_inventory(result['graph'],info)
            studio.log('H3 local : '+path.name)
            return graph,{**profile,'workflow':path.name,'inventory_changes':changes}
        except (ValueError,OSError) as e:failures.append(path.name+' : '+str(e))
    raise ValueError('Aucun workflow H3 local compatible. Les workflows Hailuo/API ne sont pas des workflows H3 locaux. '+(' | '.join(failures)[:1700] if failures else 'Le nœud MiniMaxH3ImageToVideo manque.'))


def recipe_for(p,graph,route):
    texts=[];models=[]
    for key,node in graph.items():
        for field,value in node.get('inputs',{}).items():
            if field in ('text','prompt','positive','negative','model.prompt') and isinstance(value,str):
                texts.append({'node':key,'class_type':node['class_type'],'input':field,'text':value})
            if field in ('ckpt_name','unet_name','clip_name','vae_name','projection') and isinstance(value,str):
                models.append({'node':key,'input':field,'model':value})
    digest=hashlib.sha256(json.dumps(graph,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return {'version':'S2.3','request':p.get('prompt',''),'prepared_prompt':p.get('prepared_prompt',''),'mode':p['mode'],'seed':p['seed'],'route':copy.deepcopy(route),'models':models,'effective_texts':texts,'graph_sha256':digest,'reference_asset':p.get('asset_id'),'settings':copy.deepcopy({k:p.get(k) for k in ('width','height','frames','fps','steps','denoise','style_presets')}),'quality_verified':False}


def prompt_options(p,raw):
    prepared=str(raw.get('prepared_prompt') or '').strip()
    if len(prepared)>6000:raise ValueError('Prompt préparé trop long.')
    # A prepared prompt applies only to the exact source and mode it was derived from.
    valid=raw.get('prepared_source')==p['prompt'] and raw.get('prepared_mode')==p['mode']
    p['prepared_prompt']=prepared if valid else ''
    p['prepared_source']=p['prompt'] if p['prepared_prompt'] else ''
    p['prepared_mode']=p['mode'] if p['prepared_prompt'] else ''
    p['auto_style']=raw.get('auto_style') is True
    if p['auto_style']:
        text=re.split(r'\n\s*\[Style visuel\]',p['prompt'],maxsplit=1)[0].casefold()
        rules={'bw':r'\b(?:noir et blanc|black and white)\b','fullbody':r'\b(?:corps entier|head.to.toe|full.body)\b','standing':r'\b(?:debout|standing)\b','cinematic':r'\b(?:cinématique|cinematic)\b','portrait':r'\bportrait\b'}
        found=[key for key,pattern in rules.items() if any(not re.search(r'(?:pas|sans|no|not)\s*$',text[max(0,m.start()-10):m.start()]) for m in re.finditer(pattern,text))]
        # An explicit composition keyword selects a compatible framing.
        if 'fullbody' in found:p['style_presets']=[k for k in p['style_presets'] if k!='portrait']
        if 'fullbody' in found:found=[k for k in found if k!='portrait']
        p['style_presets']=list(dict.fromkeys(p['style_presets']+found))
    p['style_preset']='+'.join(p['style_presets'])[:120]
    return p
