import json, os, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=Path(r"C:\AI\SimpleStudioV2\app\workflows.py")
OUT=ROOT/"pc-relay"/"BAZOR_DATA"/"STUDIO_WORKFLOWS_AUDIT"
OUT.mkdir(parents=True,exist_ok=True)

def main():
    if not TARGET.exists():
        raise SystemExit("missing:"+str(TARGET))
    lines=TARGET.read_text(encoding="utf-8",errors="replace").splitlines()
    ranges=[(1,80),(180,340)]
    excerpts=[]
    for a,b in ranges:
        block=[]
        for i in range(a,min(b,len(lines))+1):
            block.append({"line":i,"text":lines[i-1]})
        excerpts.append({"start":a,"end":b,"lines":block})
    keys=("MiniMax","H3","workflow","MODELS","width","height","frames","length","clip_name","vae_name","unet_name","json")
    matches=[]
    for i,line in enumerate(lines,1):
        if any(k.lower() in line.lower() for k in keys):
            matches.append({"line":i,"text":line})
    report={"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S"),"path":str(TARGET),"excerpts":excerpts,"matches":matches[:250]}
    p=OUT/"latest.json";p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"path":str(TARGET),"lines":len(lines),"report":str(p),"matches":len(matches)},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
