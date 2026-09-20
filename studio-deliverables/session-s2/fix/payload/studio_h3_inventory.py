"""Resolve the user's H3 variants against the live registry; never download models.

Qwen 4B needs the ClipProj conditioning adapter, not just a filename change.
Contract: nicolab28/ComfyUI-ClipProj clipproj_nodes.py, revision c01ba8fb.
"""
from copy import deepcopy

PAIRS={
 ('UNETLoader','unet_name','minimax_h3_fl2va_pruned_int8_convrot.safetensors'):'minimax_h3_fl2va_pruned_w4a8_mixed.safetensors',
 ('VAELoader','vae_name','minimax_h3_video_vae_fp16.safetensors'):'minimax_h3_video_vae_int8_convrot.safetensors',
 ('CLIPLoader','clip_name','qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'):'qwen3vl_4b_int8_convrot.safetensors',
}

def basename(value):return str(value).replace('\\','/').split('/')[-1]

def choices(info,kind,field):
    schema=info.get(kind,{}).get('input',{})
    spec={**schema.get('required',{}),**schema.get('optional',{})}.get(field,[])
    return spec[0] if spec and isinstance(spec[0],list) else []

def exact_available(items,name):
    matches=[v for v in items if basename(v)==name]
    if len(matches)!=1:raise ValueError('Modèle requis absent ou ambigu dans ComfyUI : '+name)
    return matches[0]

def resolve_h3_inventory(graph,info):
    graph=deepcopy(graph);changes=[]
    for key,node in list(graph.items()):
        if not isinstance(node,dict):continue
        kind=node.get('class_type');inputs=node.get('inputs',{})
        for field in ('unet_name','vae_name','clip_name'):
            current=inputs.get(field)
            if not isinstance(current,str):continue
            available=choices(info,kind,field)
            if current in available:continue
            same=[v for v in available if basename(v)==basename(current)]
            if len(same)>1:raise ValueError('Modèle ambigu dans ComfyUI : '+current)
            if same:
                inputs[field]=same[0];changes.append({'node':key,'input':field,'before':current,'after':same[0]});continue
            replacement=PAIRS.get((kind,field,basename(current)))
            if replacement:
                target=exact_available(available,replacement)
                inputs[field]=target;changes.append({'node':key,'input':field,'before':current,'after':target})
            elif available:
                raise ValueError('Le workflow demande un modèle absent : '+current+'. Aucun remplacement arbitraire.')
    # A 4B CLIP produces 2560-dimensional embeddings; H3 requires 5120.
    for key,node in list(graph.items()):
        if node.get('class_type')!='CLIPLoader':continue
        inp=node.get('inputs',{})
        if basename(inp.get('clip_name'))!='qwen3vl_4b_int8_convrot.safetensors':continue
        if 'krea2' not in choices(info,'CLIPLoader','type'):
            raise ValueError('Le chargeur CLIP installé ne propose pas le type krea2 nécessaire au Qwen 4B.')
        if 'ClipProjApply' not in info:
            raise ValueError('Qwen 4B est installé, mais le nœud ClipProjApply manque. Le 4B ne remplace pas directement le 32B de H3.')
        projection=exact_available(choices(info,'ClipProjApply','projection'),'mmh3-4b-ClipProj-v3-mlp.safetensors')
        if inp.get('type')!='krea2':changes.append({'node':key,'input':'type','before':inp.get('type'),'after':'krea2'})
        inp['type']='krea2'
        # CPU encoding avoids keeping another 4B network pinned on the 8 GB GPU.
        if 'cpu' in choices(info,'CLIPLoader','device'):inp['device']='cpu'
        projection_nodes=[(nid,n) for nid,n in graph.items() if n.get('class_type')=='ClipProjApply' and n.get('inputs',{}).get('clip')==[key,0]]
        if projection_nodes:
            projected_id,projected=projection_nodes[0];projected['inputs']['projection']=projection
        else:
            projected_id='BAZOR_H3_PROJECTION_'+str(key).replace(':','_')
            if projected_id in graph:raise ValueError('Identifiant de projection déjà utilisé.')
            graph[projected_id]={'class_type':'ClipProjApply','inputs':{'clip':[key,0],'projection':projection},'_meta':{'title':'Qwen 4B vers conditionnement H3'}}
            changes.append({'node':projected_id,'input':'projection','before':None,'after':projection})
        skip={nid for nid,_ in projection_nodes}|{projected_id}
        for nid,consumer in graph.items():
            if nid in skip:continue
            for field,value in consumer.get('inputs',{}).items():
                if value==[key,0]:consumer['inputs'][field]=[projected_id,0]
    return graph,changes
