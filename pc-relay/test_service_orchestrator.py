"""Offline tests for bounded BAZOR process orchestration."""
from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_service_orchestrator as orch
import bazor_transactional_deployer as tx

OLD_CORE, OLD_ROOM, NEW_CORE, NEW_ROOM = "a"*64, "b"*64, "c"*64, "d"*64

class FakeBackend:
    def __init__(self):
        self.identities = {
            orch.CORE_PORT: orch.ProcessIdentity("core",101,orch.CORE_PORT,OLD_CORE,True),
            orch.ROOM_PORT: orch.ProcessIdentity("room",102,orch.ROOM_PORT,OLD_ROOM,True)}
        self.stopped, self.started, self.chat_ok = [], [], True
    def inspect_port(self, port): return self.identities.get(port)
    def stop_pid(self, pid):
        self.stopped.append(pid)
        for port, identity in list(self.identities.items()):
            if identity.pid == pid: del self.identities[port]
        return True
    def wait_stopped(self, pid, timeout_seconds):
        return all(x.pid != pid for x in self.identities.values())
    def start_service(self, component, program_root, port):
        new = (program_root/"app.py").read_text().startswith("new")
        digest = ((NEW_CORE if component=="core" else NEW_ROOM) if new
                  else (OLD_CORE if component=="core" else OLD_ROOM))
        pid = 201 + len(self.started)
        self.identities[port] = orch.ProcessIdentity(component,pid,port,digest,True)
        self.started.append((component,program_root.name,pid))
        return pid
    def health(self, component, port): return True
    def local_chat(self, core_port, ollama_port, prompt):
        return self.chat_ok and prompt == orch.LOCAL_PROBE

class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.core,self.room=root/"Core",root/"Room"
        self.cc,self.cr=root/"CandidateCore",root/"CandidateRoom"
        self.txroot,self.auth=root/"Transactions",root/"authorization.json"
        for d in (self.core,self.room,self.cc,self.cr): d.mkdir()
        (self.core/"app.py").write_text("old core")
        (self.room/"app.py").write_text("old room")
        for name in tx.PROTECTED_ROOM: (self.room/name).write_text("{}")
        (self.cc/"app.py").write_text("new core"); (self.cr/"app.py").write_text("new room")
        out=tx.prepare(self.core,self.room,self.cc,self.cr,self.txroot,"tx-test")
        tx.issue_authorization(self.txroot,out["txid"],self.auth)
        self.old=(orch.ExpectedService("core",orch.CORE_PORT,OLD_CORE),
                  orch.ExpectedService("room",orch.ROOM_PORT,OLD_ROOM))
        self.new=(orch.ExpectedService("core",orch.CORE_PORT,NEW_CORE),
                  orch.ExpectedService("room",orch.ROOM_PORT,NEW_ROOM))
    def run_it(self,b):
        return orch.promote_with_runtime_verification(
            self.txroot,"tx-test",self.auth,b,self.old,self.new)
    def test_success(self):
        b=FakeBackend(); out=self.run_it(b)
        self.assertTrue(out["ok"]); self.assertEqual(b.stopped,[102,101])
    def test_identity_mismatch_refuses_before_stop(self):
        b=FakeBackend()
        b.identities[orch.CORE_PORT]=orch.ProcessIdentity("core",101,orch.CORE_PORT,"f"*64,True)
        with self.assertRaisesRegex(RuntimeError,"service_identity_mismatch"): self.run_it(b)
        self.assertEqual(b.stopped,[]); self.assertTrue(self.auth.exists())
    def test_unowned_process_refuses(self):
        b=FakeBackend()
        b.identities[orch.ROOM_PORT]=orch.ProcessIdentity("room",102,orch.ROOM_PORT,OLD_ROOM,False)
        with self.assertRaises(RuntimeError): self.run_it(b)
        self.assertEqual(b.stopped,[])
    def test_health_failure_rolls_back_and_restarts_old(self):
        b=FakeBackend(); calls={"room":0}
        def health(component,port):
            if component=="room":
                calls["room"]+=1; return calls["room"]>1
            return True
        b.health=health; out=self.run_it(b)
        self.assertFalse(out["ok"]); self.assertTrue(out["rollback_ok"])
        self.assertTrue(out["old_services_restored"])
        self.assertEqual((self.core/"app.py").read_text(),"old core")
    def test_local_chat_failure_rolls_back(self):
        b=FakeBackend(); calls={"n":0}
        def chat(*args): calls["n"]+=1; return calls["n"]>1
        b.local_chat=chat; out=self.run_it(b)
        self.assertFalse(out["ok"]); self.assertTrue(out["rollback_ok"])
        self.assertTrue(out["old_services_restored"])
    def test_public_summary_closed_vocabulary(self):
        text=orch.public_summary({"ok":False,"phase":"secret path","rollback_ok":False})
        self.assertIn("PHASE: MANUAL_REQUIRED",text)
        self.assertIn("PAID_AI_CALLS: ZERO",text); self.assertNotIn("secret path",text)

if __name__=="__main__": unittest.main()
