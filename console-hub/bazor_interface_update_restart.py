import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "pc-relay" / "BAZOR_DATA" / "HUB_LOGS"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG = LOG_DIR / "interface_update_restart.log"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

def log(msg):
    line=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with LOG.open("a",encoding="utf-8") as f:
            f.write(line+"\n")
    except Exception:
        pass

def run():
    log("=== UPDATE + RELANCE demandée via interface ===")
    try:
        p=subprocess.run(["git","-C",str(ROOT),"pull","--ff-only"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120,creationflags=CREATE_NO_WINDOW)
        log("git pull rc="+str(p.returncode))
        if p.stdout.strip(): log(p.stdout.strip()[-3000:])
        if p.stderr.strip(): log(p.stderr.strip()[-3000:])
        if p.returncode != 0:
            return 2
    except Exception as e:
        log("git pull erreur: "+type(e).__name__+": "+str(e))
        return 3

    launcher=ROOT / "LANCER_BAZOR_MOBILE_TOUT_EN_UN.cmd"
    if not launcher.exists():
        log("launcher absent: "+str(launcher))
        return 4

    try:
        # Laisse la réponse HTTP partir avant le nettoyage/redémarrage.
        time.sleep(1.2)
        flags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(["cmd.exe","/c",str(launcher)],cwd=str(ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        log("launcher déclenché")
        return 0
    except Exception as e:
        log("launcher erreur: "+type(e).__name__+": "+str(e))
        return 5

if __name__=="__main__":
    raise SystemExit(run())
