"""Tests for the Windows process backend; live process test is disposable."""
from __future__ import annotations
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_windows_process_backend as win

CORE = win.LaunchSpec("fixture.py", "/api/v1/health", "BAZOR API")
ROOM = win.LaunchSpec("fixture.py", "/health")

FIXTURE = r"""
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
kind=os.environ["BAZOR_COMPONENT"]
port=int(os.environ["BAZOR_CORE_PORT"] if kind=="core" else os.environ["BAZOR_ROOM_PORT"])
class H(BaseHTTPRequestHandler):
 def sendj(self,x):
  b=json.dumps(x).encode(); self.send_response(200); self.send_header("Content-Type","application/json")
  self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  if kind=="core" and self.path=="/api/v1/health":
   return self.sendj({"ok":True,"service":"BAZOR API","pid":os.getpid(),"ollama":{"online":True},
    "external_secret_present":any(any(x in k.upper() for x in ("API_KEY","TOKEN","SECRET","PASSWORD","CREDENTIAL"))
                                  for k in os.environ),
    "budget":os.environ.get("BAZOR_EXTERNAL_BUDGET"),
    "mammouth_budget":os.environ.get("BAZOR_MAMMOUTH_BUDGET_USD")})
  if kind=="room" and self.path=="/health": return self.sendj({"ok":True})
  self.send_error(404)
 def do_POST(self):
  if kind=="core" and self.path=="/api/v1/chat":
   return self.sendj({"ok":True,"ollama":{"ok":True,"provider":"ollama","answer":"BAZOR_LOCAL_OK"}})
  self.send_error(404)
 def log_message(self,*a): pass
ThreadingHTTPServer(("127.0.0.1",port),H).serve_forever()
"""

def free_port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p

class ParserTests(unittest.TestCase):
    def test_child_environment_removes_unknown_provider_secrets_and_zeroes_budget(self):
        env=win.child_environment({"PATH":"keep","NOTRACK_API_KEY":"private",
            "OPENROUTER_TOKEN":"private","OTHER_PASSWORD":"private",
            "MAMMOUTH_KEY":"private",
            "BAZOR_MAMMOUTH_BUDGET_USD":"999"},"core",{"core":8875,"room":8768})
        self.assertEqual(env["PATH"],"keep")
        self.assertNotIn("NOTRACK_API_KEY",env)
        self.assertNotIn("OPENROUTER_TOKEN",env)
        self.assertNotIn("OTHER_PASSWORD",env)
        self.assertNotIn("MAMMOUTH_KEY",env)
        self.assertEqual(env["BAZOR_MAMMOUTH_BUDGET_USD"],"0")
        self.assertEqual(env["BAZOR_CORE_URL"],"http://127.0.0.1:8875")
    def test_loopback_listener(self):
        data="  TCP    127.0.0.1:8775   0.0.0.0:0   LISTENING   1234\n"
        self.assertEqual(win.parse_netstat_listeners(data,8775),{1234})
    def test_wildcard_listener_is_rejected(self):
        data="  TCP    0.0.0.0:8775   0.0.0.0:0   LISTENING   1234\n"
        with self.assertRaisesRegex(RuntimeError,"non_loopback_listener"):
            win.parse_netstat_listeners(data,8775)
    def test_french_listener_state(self):
        data="  TCP    127.0.0.1:8775   0.0.0.0:0   ÉCOUTE   1234\n"
        self.assertEqual(win.parse_netstat_listeners(data,8775),{1234})
    def test_wrong_port_ignored(self):
        data="  TCP    127.0.0.1:9999   0.0.0.0:0   LISTENING   1234\n"
        self.assertEqual(win.parse_netstat_listeners(data,8775),set())
    def test_process_mutation_disabled_by_default(self):
        b=win.WindowsProcessBackend({"core":CORE,"room":ROOM},{"core":8775,"room":8765})
        with self.assertRaisesRegex(RuntimeError,"process_changes_disabled"):
            b.stop_pid(123)
    def test_unapproved_pid_is_never_stopped(self):
        b=win.WindowsProcessBackend(
            {"core":CORE,"room":ROOM},{"core":8775,"room":8765},True)
        self.assertFalse(b.stop_pid(123))
    def test_non_exact_local_reply_is_refused(self):
        b=win.WindowsProcessBackend({"core":CORE,"room":ROOM},{"core":8775,"room":8765})
        b._json_request=lambda *args,**kwargs: {"ok":True,"ollama":{
            "ok":True,"provider":"ollama","answer":"NOT BAZOR_LOCAL_OK"}}
        self.assertFalse(b.local_chat(8775,11434,"probe"))

@unittest.skipUnless(os.name=="nt","Windows integration only")
class WindowsDisposableProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); self.core=root/"Core"; self.room=root/"Room"
        self.core.mkdir(); self.room.mkdir()
        (self.core/"fixture.py").write_text(FIXTURE,encoding="utf-8")
        (self.room/"fixture.py").write_text(FIXTURE,encoding="utf-8")
        self.cp,self.rp=free_port(),free_port()
        self.backend=win.WindowsProcessBackend(
            {"core":CORE,"room":ROOM},{"core":self.cp,"room":self.rp},True)
        self.pids=[]
        self.addCleanup(self.cleanup_processes)
    def cleanup_processes(self):
        for pid in self.pids:
            identity=self.backend._approved.get(pid)
            if identity and self.backend._is_alive(pid): self.backend.stop_pid(pid)
            self.backend.wait_stopped(pid,3)
    def wait_identity(self,port):
        deadline=time.time()+10
        while time.time()<deadline:
            identity=self.backend.inspect_port(port)
            if identity: return identity
            time.sleep(.1)
        self.fail("listener identity timeout")
    def test_real_loopback_process_identity_health_chat_and_stop(self):
        os.environ["MAMMOUTH_API_KEY"]="MUST_NOT_REACH_CHILD"
        self.addCleanup(os.environ.pop,"MAMMOUTH_API_KEY",None)
        os.environ["NOTRACK_API_KEY"]="MUST_NOT_REACH_CHILD"
        self.addCleanup(os.environ.pop,"NOTRACK_API_KEY",None)
        os.environ["BAZOR_MAMMOUTH_BUDGET_USD"]="999"
        self.addCleanup(os.environ.pop,"BAZOR_MAMMOUTH_BUDGET_USD",None)
        core_pid=self.backend.start_service("core",self.core,self.cp); self.pids.append(core_pid)
        room_pid=self.backend.start_service("room",self.room,self.rp); self.pids.append(room_pid)
        core=self.wait_identity(self.cp); room=self.wait_identity(self.rp)
        self.assertEqual((core.pid,room.pid),(core_pid,room_pid))
        self.assertTrue(core.owned_by_current_user and room.owned_by_current_user)
        self.assertEqual(core.executable_sha256,win.sha256_file(Path(sys.executable)))
        self.assertTrue(self.backend.health("core",self.cp))
        core_health=self.backend._health_json("core",self.cp)
        self.assertFalse(core_health["external_secret_present"])
        self.assertEqual(core_health["budget"],"0")
        self.assertEqual(core_health["mammouth_budget"],"0")
        self.assertTrue(self.backend.health("room",self.rp))
        self.assertTrue(self.backend.local_chat(self.cp,11434,"Reponds BAZOR_LOCAL_OK"))
        self.assertTrue(self.backend.stop_pid(room_pid))
        self.assertTrue(self.backend.wait_stopped(room_pid,5))
        self.assertTrue(self.backend.stop_pid(core_pid))
        self.assertTrue(self.backend.wait_stopped(core_pid,5))

if __name__=="__main__": unittest.main()
