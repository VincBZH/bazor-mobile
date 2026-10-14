"""Offline tests: mocked Core and Action Engine; never touch the user's Windows."""
import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bazor_ollama_action_planner import ActionScope, run_bounded_task

BEFORE = b"def f():\n    return 'old'\n"
AFTER = "def f():\n    return 'new'\n"
SCOPE = ActionScope(
    task_id="MECANO-P0-002", project_id="bazor-tools", root="bazor_repo",
    path="pc-relay/bazor_example.py", operation="replace",
    instructions="Safely change the example return value.",
    expected_sha256=hashlib.sha256(BEFORE).hexdigest(),
    find_must_contain=("return 'old'",), replace_must_contain=("return 'new'",),
)
GOOD = {"op":"replace","root":"bazor_repo","path":"pc-relay/bazor_example.py",
        "find":BEFORE.decode(),"replace":AFTER,"expected_count":1}


class FakeEngine:
    def __init__(self):
        self.calls = []

    def parse_actions(self, answer):
        if not answer.startswith("BAZOR_ACTIONS: "):
            return []
        return json.loads(answer.split(": ", 1)[1])["actions"]

    def apply(self, project, actions, request_id):
        self.calls.append((project, actions, request_id))
        return {"ok":True,"applied":True,"preflight":{"ok":True},
                "files":[{"root":actions[0]["root"],"path":actions[0]["path"]}],
                "tests":[{"ok":True}],"backup_dir":"BACKUPS/TEST"}


def reply(actions, **extras):
    out = {"provider_requested":"ollama","engine":"ollama",
           "model":"qwen2.5-coder:7b","ok":True,
           "answer":"BAZOR_ACTIONS: " + json.dumps({"actions":actions})}
    out.update(extras)
    return out


def run(outputs, scope=SCOPE, engine=None, read=None):
    eng = engine or FakeEngine()
    observed = []
    def core(payload):
        observed.append(payload)
        value = outputs[len(observed) - 1]
        if isinstance(value, Exception):
            raise value
        return value
    result = run_bounded_task(core, eng, scope, read or (lambda _root, _path: BEFORE))
    return result, eng, observed


class TestPlanner(unittest.TestCase):
    def test_valid_action_applied_once(self):
        r,e,p = run([reply([GOOD])])
        self.assertEqual(r["status"], "DONE")
        self.assertEqual(len(e.calls), 1)
        self.assertEqual(r["attempts"], 1)

    def test_zero_actions_one_retry(self):
        r,e,p = run([reply([]), reply([GOOD])])
        self.assertEqual(r["status"], "DONE")
        self.assertEqual(r["attempts"], 2)
        self.assertEqual(len(e.calls), 1)
        self.assertEqual(p[1]["provider"], "ollama")
        self.assertTrue(p[1]["repair"])
        self.assertEqual(p[1]["previous"], "")

    def test_two_actions_then_valid(self):
        r,e,p = run([reply([GOOD, GOOD]), reply([GOOD])])
        self.assertEqual(r["status"], "DONE")
        self.assertEqual(len(e.calls), 1)

    def test_repeat_failure_no_apply(self):
        r,e,p = run([reply([]), reply([])])
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["attempts"], 2)
        self.assertEqual(len(e.calls), 0)

    def test_forged_provider_no_retry(self):
        r,e,p = run([reply([GOOD], engine="mammouth"), reply([GOOD])])
        self.assertEqual(r["reason"], "provider_not_proven_ollama")
        self.assertEqual(len(p), 1)

    def test_requested_paid_provider_no_retry(self):
        r,e,p = run([reply([GOOD], provider_requested="auto"), reply([GOOD])])
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(len(p), 1)

    def test_bad_path_rejected_then_retry(self):
        bad = dict(GOOD, path="../escape.py")
        r,e,p = run([reply([bad]), reply([GOOD])])
        self.assertEqual(r["status"], "DONE")
        self.assertEqual(len(e.calls), 1)

    def test_unsafe_replace_rejected(self):
        bad = dict(GOOD, replace="exec(0)")
        r,e,p = run([reply([bad]), reply([])])
        self.assertEqual(r["status"], "BLOCKED")
        self.assertFalse(e.calls)

    def test_sha_mismatch_halts(self):
        r,e,p = run([reply([GOOD]), reply([GOOD])], read=lambda *_: b"changed")
        self.assertEqual(r["reason"], "target_sha256_mismatch")
        self.assertEqual(len(p), 0)
        self.assertFalse(e.calls)

    def test_bad_action_extra_fields(self):
        bad = dict(GOOD, shell="rm -rf /")
        r,e,p = run([reply([bad]), reply([])])
        self.assertEqual(r["status"], "BLOCKED")
        self.assertFalse(e.calls)

    def test_action_engine_failure_not_success(self):
        class F(FakeEngine):
            def apply(self, *args, **kwargs):
                return {"ok":False,"error":"preflight_failed","preflight":{"ok":False}}
        r,e,p = run([reply([GOOD])], engine=F())
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["attempts"], 1)

    def test_exception_scrubbed(self):
        r,e,p = run([RuntimeError("private API key=secret")])
        self.assertEqual(r["reason"], "core_error_RuntimeError")
        self.assertNotIn("secret", str(r))

    def test_invalid_scope_no_request(self):
        bad = replace(SCOPE, path="../private.txt")
        r,e,p = run([reply([GOOD])], scope=bad)
        self.assertEqual(r["reason"], "invalid_local_scope")
        self.assertEqual(len(p), 0)

    def test_template_json_and_local_source_excerpt(self):
        r,e,p = run([reply([GOOD])])
        template = p[0]["task"].split("BAZOR_ACTIONS: ", 1)[1].split("\n", 1)[0]
        parsed = json.loads(template)
        self.assertEqual(len(parsed["actions"]), 1)
        self.assertIn("return 'old'", p[0]["task"])

    def test_source_anchor_required_before_core(self):
        scope = replace(SCOPE, find_must_contain=())
        r,e,p = run([reply([GOOD])], scope=scope)
        self.assertEqual(r["reason"], "source_anchor_required")
        self.assertEqual(len(p), 0)

    def test_source_anchor_missing_before_core(self):
        scope = replace(SCOPE, find_must_contain=("missing text",))
        r,e,p = run([reply([GOOD])], scope=scope)
        self.assertEqual(r["reason"], "source_anchor_missing")
        self.assertEqual(len(p), 0)

    def test_missing_model_no_retry(self):
        r,e,p = run([reply([GOOD], model="")])
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(len(p), 1)


if __name__ == "__main__":
    unittest.main()
