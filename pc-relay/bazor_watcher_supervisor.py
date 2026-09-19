from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHER = ROOT / "pc-relay" / "bazor_github_watcher.py"
LOG_DIR = ROOT / "pc-relay" / "BAZOR_DATA" / "HUB_LOGS"
SUPERVISOR_LOG = LOG_DIR / "watcher_supervisor.log"
WATCHER_LOG = LOG_DIR / "watcher.log"
LOCK_PORT = 48765
RESTART_DELAY = 3
HEARTBEAT_SECONDS = 30


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with SUPERVISOR_LOG.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(f"[{stamp}] {message}\n")


def acquire_singleton() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        sock.listen(1)
        return sock
    except OSError:
        log("supervisor already active; exiting duplicate")
        raise SystemExit(0)


def current_head() -> str:
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (cp.stdout or "").strip() if cp.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def start_watcher() -> subprocess.Popen:
    if not WATCHER.exists():
        raise FileNotFoundError(str(WATCHER))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = WATCHER_LOG.open("a", encoding="utf-8", errors="replace", buffering=1)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [sys.executable, "-u", str(WATCHER)],
        cwd=str(ROOT),
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=True,
    )
    log(f"watcher started pid={proc.pid} python={sys.executable} head={current_head()} watcher={WATCHER}")
    return proc


def main() -> int:
    _lock = acquire_singleton()
    log(f"supervisor boot python={sys.executable} head={current_head()} root={ROOT}")
    proc = None
    last_heartbeat = 0.0
    while True:
        try:
            if proc is None or proc.poll() is not None:
                if proc is not None:
                    log(f"watcher exited rc={proc.returncode}; restarting")
                    time.sleep(RESTART_DELAY)
                proc = start_watcher()

            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                log(f"supervisor alive watcher_pid={proc.pid} watcher_rc={proc.poll()} head={current_head()}")
                last_heartbeat = now
            time.sleep(1)
        except KeyboardInterrupt:
            if proc is not None and proc.poll() is None:
                proc.terminate()
            log("supervisor stopped by user")
            return 0
        except Exception as exc:
            log(f"supervisor error {type(exc).__name__}: {exc}")
            time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    raise SystemExit(main())
