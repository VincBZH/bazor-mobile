import json, os, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = Path(r"C:\AI\SimpleStudioV2")
COMFY = Path(r"C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI")
OUT = ROOT / "pc-relay" / "BAZOR_DATA" / "H3_CONNECTION_AUDIT"
OUT.mkdir(parents=True, exist_ok=True)

TARGET = "MiniMax_H3_FL2V_8GB_VRAM.json"
BAD = {
  "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors":"qwen3vl_4b_int8_convrot.safetensors",
  "minimax_h3_video_vae_fp16.safetensors":"minimax_h3_video_vae_int8_convrot.safetensors",
  "minimax_h3_fl2va_pruned_int8_convrot.safetensors":"minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
}
PRUNE={".git","node_modules","models","checkpoints","output","outputs","temp","tmp","cache","__pycache__","logs","log","backup","backups",".venv","venv","downloads"}
TEXT_EXTS={".json",".py",".js",".ts",".tsx",".jsx",".html",".ps1",".cmd",".bat",".yml",".yaml",".toml",".ini",".cfg"}

def http_json(url, timeout=8):
    req=urllib.request.Request(url,headers={"User-Agent":"BAZOR-H3-Connection-Audit/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def walk(root, exts=None, limit=10000):
    out=[]
    if not root.exists(): return out
    for cur,dirs,names in os.walk(root,topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in PRUNE]
        for n in names:
            p=Path(cur)/n
            if exts and p.suffix.lower() not in exts: continue
            out.append(p)
            if len(out)>=limit: return out
    return out

def read(p):
    try: return p.read_text(encoding="utf-8-sig",errors="replace")
    except Exception: return ""

def find_workflows():
    hits=[]
    for base in (STUDIO,COMFY):
        for p in walk(base,{".json"}):
            if p.name.lower()==TARGET.lower():
                hits.append(str(p))
    return hits

def recursive_nodes(obj, node_id=None, out=None):
    if out is None: out=[]
    if isinstance(obj,dict):
        if isinstance(obj.get("class_type"),str) and isinstance(obj.get("inputs"),dict):
            out.append({"id":node_id,"class_type":obj.get("class_type"),"inputs":obj.get("inputs")})
        for k,v in obj.items():
            recursive_nodes(v, k if isinstance(v,dict) else node_id, out)
    elif isinstance(obj,list):
        for v in obj: recursive_nodes(v,node_id,out)
    return out

def object_info():
    data=http_json("http://127.0.0.1:8188/object_info")
    out={"loaders":{},"dimension_classes":[]}
    for cls in ("CLIPLoader","VAELoader","UNETLoader"):
        req=((data.get(cls) or {}).get("input") or {}).get("required") or {}
        opts={}
        for k,v in req.items():
            if isinstance(v,list) and v and isinstance(v[0],list): opts[k]=v[0]
        out["loaders"][cls]=opts
    dimkeys={"width","height","frames","num_frames","length","video_length","frame_count","fps"}
    for cls,node in data.items():
        req=((node.get("input") or {}).get("required") or {})
        keys=[k for k in req if str(k).lower() in dimkeys]
        if keys: out["dimension_classes"].append({"class_type":cls,"keys":keys})
    return out

def audit_workflow(path):
    raw=read(Path(path))
    data=json.loads(raw)
    nodes=recursive_nodes(data)
    loaders=[]; dims=[]; bad=[]
    for n in nodes:
        ins=n["inputs"]
        for k,v in ins.items():
            kl=str(k).lower()
            if kl in ("clip_name","vae_name","unet_name"):
                loaders.append({"node_id":n["id"],"class_type":n["class_type"],"input":k,"value":v})
                if isinstance(v,str) and v in BAD:
                    bad.append({"node_id":n["id"],"class_type":n["class_type"],"input":k,"bad":v,"replacement":BAD[v]})
            if kl in ("width","height","frames","num_frames","length","video_length","frame_count","fps"):
                dims.append({"node_id":n["id"],"class_type":n["class_type"],"input":k,"value":v})
    return {"path":path,"node_count":len(nodes),"loaders":loaders,"dimensions":dims,"bad_values":bad}

def active_refs():
    hits=[]
    needles=list(BAD.keys())+[TARGET,"largeur/hauteur","width","height","clip_name","vae_name","unet_name"]
    for p in walk(STUDIO,TEXT_EXTS):
        txt=read(p); low=txt.lower()
        matched=[n for n in needles if n.lower() in low]
        if not matched: continue
        lines=[]
        for i,line in enumerate(txt.splitlines(),1):
            if any(n.lower() in line.lower() for n in matched):
                lines.append({"line":i,"text":line[:600]})
                if len(lines)>=40: break
        hits.append({"path":str(p),"matches":matched,"lines":lines})
    return hits

def main():
    report={
      "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S"),
      "studio_exists":STUDIO.exists(),
      "comfy_exists":COMFY.exists(),
      "object_info":{},
      "workflows":[],
      "active_refs":[],
    }
    report["object_info"]=object_info()
    for p in find_workflows():
        report["workflows"].append(audit_workflow(p))
    report["active_refs"]=active_refs()
    latest=OUT/"latest.json"
    latest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={
      "workflow_count":len(report["workflows"]),
      "bad_workflow_values":sum(len(x["bad_values"]) for x in report["workflows"]),
      "dimension_fields":sum(len(x["dimensions"]) for x in report["workflows"]),
      "active_reference_files":len(report["active_refs"]),
      "report_file":str(latest),
    }
    print(json.dumps(summary,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
