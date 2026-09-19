import unittest, json
from protocol import evaluate, run_rules
RULES=json.load(open("rules.json",encoding="utf-8"))
class ProtocolTests(unittest.TestCase):
    def test_and(self):
        self.assertTrue(evaluate({"ET":[{"field":"a","op":"eq","value":1},{"field":"b","op":"truthy"}]},{"a":1,"b":2}))
    def test_or(self):
        self.assertTrue(evaluate({"OU":[{"field":"a","op":"eq","value":2},{"field":"a","op":"eq","value":1}]},{"a":1}))
    def test_handoff_012(self):
        out=run_rules(RULES,{"task_id":"STUDIO-P0-012","task_status":"DONE","proof":{"preflight_ok":True,"tests_ok":True}})
        self.assertTrue(any(x.get("action")=="handoff" and x.get("next_task")=="STUDIO-P0-010" for x in out))
    def test_handoff_010(self):
        out=run_rules(RULES,{"task_id":"STUDIO-P0-010","task_status":"VERIFIE","proof":{"preflight_ok":True,"tests_ok":True}})
        self.assertTrue(any(x.get("action")=="handoff" and x.get("next_task")=="STUDIO-P0-011" for x in out))
    def test_no_handoff_without_proof(self):
        out=run_rules(RULES,{"task_id":"STUDIO-P0-012","task_status":"DONE","proof":{"preflight_ok":False,"tests_ok":True}})
        self.assertFalse(any(x.get("action")=="handoff" for x in out))
    def test_whitelist(self):
        bad={"rules":[{"SI":{"field":"x","op":"eq","value":1},"ALORS":[{"action":"shell","cmd":"whoami"}]}]}
        self.assertEqual(run_rules(bad,{"x":1}),[])
if __name__=="__main__": unittest.main()
