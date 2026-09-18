import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "pc-relay" / "BAZOR_DATA" / "HUB_LOGS"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG = LOG_DIR / "popup_guard.log"
LOCK_PORT = 8792
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

BAZOR_MARKERS = (
    "bazor", "bazor-mobile", "127.0.0.1:8775", "127.0.0.1:8776",
    "127.0.0.1:8765", "127.0.0.1:8766", "127.0.0.1:8188",
    "127.0.0.1:8191", ":8775", ":8776"
)

def log(msg):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def ps_json(script):
    try:
        p = subprocess.run(
            ["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",script],
            capture_output=True,text=True,encoding="utf-8",errors="replace",
            timeout=6,creationflags=CREATE_NO_WINDOW
        )
        if p.returncode or not p.stdout.strip():
            return []
        data=json.loads(p.stdout)
        return data if isinstance(data,list) else [data]
    except Exception:
        return []

def kill_pid(pid):
    if not pid:
        return
    try:
        subprocess.run(["taskkill","/PID",str(int(pid)),"/T","/F"],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       timeout=4,creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass

def is_bazor(text):
    t=(text or "").lower()
    return any(x in t for x in BAZOR_MARKERS)

def scan_once():
    procs=ps_json(
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    by_pid={int(p.get("ProcessId") or 0):p for p in procs}
    for p in procs:
        name=str(p.get("Name") or "").lower()
        if name!="curl.exe":
            continue
        pid=int(p.get("ProcessId") or 0)
        cmd=str(p.get("CommandLine") or "")
        parent=by_pid.get(int(p.get("ParentProcessId") or 0),{})
        pcmd=str(parent.get("CommandLine") or "")
        pname=str(parent.get("Name") or "")
        if is_bazor(cmd) or is_bazor(pcmd):
            log(f"KILL curl PID={pid} CMD={cmd} PARENT={pname} {pcmd}")
            kill_pid(pid)
            # If an obsolete wrapper is repeatedly spawning BAZOR curl, stop that wrapper too.
            if pname.lower() in ("cmd.exe","powershell.exe","pwsh.exe") and "curl" in pcmd.lower() and is_bazor(pcmd):
                ppid=int(parent.get("ProcessId") or 0)
                log(f"KILL parent loop PID={ppid} CMD={pcmd}")
                kill_pid(ppid)

def single_instance():
    s=socket.socket()
    try:
        s.bind(("127.0.0.1",LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None

def main():
    lock=single_instance()
    if not lock:
        return 0
    log("Popup Guard actif")
    while True:
        scan_once()
        time.sleep(0.45)

if __name__=="__main__":
    raise SystemExit(main())
