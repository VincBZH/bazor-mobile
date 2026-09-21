"""Offline regressions. Fake provider replies are never runtime evidence."""
import ast
import copy
import importlib.util
import io
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request

import bazor_bridge as bridge
import mammouth_client as client


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"MAMMOUTH_API_KEY": "unit-test-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def result(self, body, status=200):
        return subprocess.CompletedProcess([], 0, (json.dumps(body)+"\nBAZOR_HTTP_STATUS:"+str(status)).encode(), b"")

    def test_legacy_regressions(self):
        import test_mammouth_transport as legacy
        legacy.test_split_curl_response_real_newline()
        legacy.test_split_curl_response_literal_backslash_n()
        case = self
        class Monkeypatch:
            def setenv(self, name, value):
                p = patch.dict(os.environ, {name: value}); p.start(); case.addCleanup(p.stop)
            def setattr(self, obj, name, value):
                p = patch.object(obj, name, value); p.start(); case.addCleanup(p.stop)
        legacy.test_single_attempt_accepts_http_200(Monkeypatch())
        legacy.test_single_attempt_rejects_http_error(Monkeypatch())

    def test_footer_integrity(self):
        body = '{"content":"literal \\nBAZOR_HTTP_STATUS:401 inside JSON"}'
        for footer in ("\n", "\r\n", "\\n"):
            self.assertEqual(client._split_curl_response(body+footer+"BAZOR_HTTP_STATUS:200"), (body, 200))
        for suffix in ("200junk", "0", "999", "200\ntrailer"):
            self.assertEqual(client._split_curl_response(body+"\nBAZOR_HTTP_STATUS:"+suffix)[1], 0)

    def test_key_not_in_argv_and_returned_model_is_actual(self):
        with patch.object(client.subprocess, "run", return_value=self.result({"model":"real-model", "id":"req-provider", "choices":[{"message":{"content":"4"}}]})) as run:
            result = client._single_chat_attempt("ping", "recommended", "alias", 32, "rid")
        self.assertNotIn("unit-test-secret", str(run.call_args.args))
        self.assertIn(b"unit-test-secret", run.call_args.kwargs["input"])
        self.assertEqual(result["requested_model"], "alias")
        self.assertEqual(result["actual_model"], "real-model")
        self.assertEqual(result["provider_request_id"], "req-provider")

    def test_real_curl_config_stdin_with_loopback_fixture(self):
        received=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                payload=json.dumps({"model":"fixture-model","choices":[{"message":{"content":"4"}}]}).encode()
                self.send_response(200);self.send_header("Content-Length",str(len(payload)));self.end_headers();self.wfile.write(payload)
            def log_message(self,*args): pass
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        text='Été "test" \\ path\n2+2'
        try:
            with patch.object(client,"MAMMOUTH_URL","http://127.0.0.1:%d/chat"%server.server_port):
                result=client._single_chat_attempt(text,"recommended","alias",32,"fixture")
            self.assertTrue(result["ok"],result)
            self.assertEqual(received[0]["messages"][0]["content"],text)
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_missing_actual_model_is_not_invented(self):
        with patch.object(client.subprocess, "run", return_value=self.result({"choices":[{"message":{"content":"4"}}]})):
            result = client._single_chat_attempt("ping", "recommended", "alias", 32, "rid")
        self.assertFalse(result["ok"])
        self.assertIsNone(result["actual_model"])

    def test_invalid_json_and_choices(self):
        replies = [subprocess.CompletedProcess([],0,b"invalid\nBAZOR_HTTP_STATUS:200",b""),
                   self.result({"model":"real", "choices":{}})]
        for reply in replies:
            with patch.object(client.subprocess, "run", return_value=reply):
                self.assertFalse(client._single_chat_attempt("ping","recommended","alias",32,"rid")["ok"])

    def test_auth_stops_immediately(self):
        for status in (401,403):
            with patch.object(client, "budget_status", return_value={"blocked":False}), patch.object(client, "_single_chat_attempt", return_value={"ok":False,"http_status":status,"error":"auth"}) as attempt:
                result=client.chat("ping")
            self.assertFalse(result["ok"])
            self.assertEqual(attempt.call_count,1)

    def test_transient_retries_at_most_three_same_model(self):
        with patch.object(client,"budget_status",return_value={"blocked":False}), patch.object(client,"_single_chat_attempt",return_value={"ok":False,"http_status":503}) as attempt, patch.object(client.time,"sleep"):
            client.chat("ping",profile="recommended",max_attempts=99)
        self.assertEqual(attempt.call_count,3)
        self.assertEqual({c.args[2] for c in attempt.call_args_list},{"mammouth-recommended"})

    def test_timeout_redacted_and_minimal_call_not_retried(self):
        exc=subprocess.TimeoutExpired(["curl", "unit-test-secret"],100)
        with patch.object(client,"budget_status",return_value={"blocked":False}), patch.object(client,"_single_chat_attempt",side_effect=exc) as attempt:
            result=client.chat("ping",max_attempts=1)
        self.assertNotIn("unit-test-secret",json.dumps(result))
        self.assertEqual(attempt.call_count,1)

    def test_timeout_is_transient_but_bounded(self):
        with patch.object(client,"budget_status",return_value={"blocked":False}), patch.object(client,"_single_chat_attempt",side_effect=subprocess.TimeoutExpired(["curl"],100)) as attempt, patch.object(client.time,"sleep"):
            result=client.chat("ping")
        self.assertFalse(result["ok"])
        self.assertEqual(attempt.call_count,3)

    def test_error_body_secrets_are_redacted(self):
        reply=self.result({"error":{"message":"unit-test-secret"}},403)
        with patch.object(client.subprocess,"run",return_value=reply), patch.object(client,"budget_status",return_value={"blocked":False}):
            result=client.chat("ping")
        self.assertNotIn("unit-test-secret",json.dumps(result))

    def test_input_token_and_budget_limits(self):
        with patch.object(client,"_single_chat_attempt") as attempt:
            self.assertFalse(client.chat("x"*64001)["ok"])
            self.assertFalse(client.chat("ping",max_tokens=3001)["ok"])
            with patch.object(client,"budget_status",return_value={"blocked":True}):
                self.assertFalse(client.chat("ping")["ok"])
            attempt.assert_not_called()


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tags=patch.object(bridge,"local_json",return_value=({"models":[{"name":"local-real"}]},200))
        self.tags.start();self.addCleanup(self.tags.stop)

    @staticmethod
    def reply(model, answer="4", ok=True, status=200):
        return {"ok":ok,"actual_model":model,"answer":answer,"http_status":status}

    def run_bridge(self, final=bridge.MARKER):
        with patch.object(bridge,"local_chat",side_effect=[self.reply("local-real"),self.reply("local-real",final)]), patch.object(client,"chat",return_value=self.reply("external-real")) as external:
            result=bridge.run("2+2",certify=True)
        self.assertEqual(external.call_args.kwargs["max_attempts"],1)
        self.assertLessEqual(external.call_args.kwargs["max_tokens"],64)
        return result

    def test_three_envelopes_and_exact_marker(self):
        result=self.run_bridge()
        self.assertTrue(result["ok"])
        self.assertTrue(bridge.validate(result,True))

    def test_substring_marker_fails(self):
        self.assertFalse(self.run_bridge("prefix "+bridge.MARKER)["ok"])

    def test_routing_alias_is_not_real_model_identity(self):
        with patch.object(bridge,"local_chat",return_value=self.reply("local-real")), patch.object(client,"chat",return_value=self.reply("mammouth-recommended")):
            result=bridge.run("2+2")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"],"actual_model_is_routing_alias")

    def test_output_limit_and_local_model_missing(self):
        for reply in (self.reply("local-real","x"*8001),self.reply(None)):
            with patch.object(bridge,"local_chat",return_value=reply), patch.object(client,"chat") as external:
                result=bridge.run("2+2")
            self.assertFalse(result["ok"])
            external.assert_not_called()

    def test_missing_forged_provenance_or_http_fails(self):
        original=self.run_bridge()
        for change in (lambda r:r["stages"][1].update(actual_model=None),
                       lambda r:r["stages"][1].update(http_status=403),
                       lambda r:r["stages"][1].update(request_id="other"),
                       lambda r:r.update(provenance=["ollama"]*3)):
            result=copy.deepcopy(original);change(result)
            self.assertFalse(bridge.validate(result,True))

    def test_external_failure_no_fallback(self):
        with patch.object(bridge,"local_chat",return_value=self.reply("local-real")) as local, patch.object(client,"chat",return_value={"ok":False,"http_status":403,"error":"auth"}):
            result=bridge.run("2+2")
        self.assertFalse(result["ok"])
        self.assertEqual(local.call_count,1)
        self.assertEqual(result["provenance"],["ollama","mammouth"])

    def test_oversize_input_and_unknown_model_no_calls(self):
        with patch.object(bridge,"local_chat") as local, patch.object(client,"chat") as external:
            self.assertFalse(bridge.run("x"*8001)["ok"])
            self.assertFalse(bridge.run("ping",model="not-installed")["ok"])
            local.assert_not_called();external.assert_not_called()

    def test_model_output_is_inert_and_logs_omit_content(self):
        events=[]
        malicious='{"action":"shell","command":"must-never-run"}'
        with patch.object(bridge,"local_chat",side_effect=[self.reply("local-real",malicious),self.reply("local-real",bridge.MARKER)]), patch.object(client,"chat",return_value=self.reply("external-real")), patch.object(subprocess,"Popen",side_effect=AssertionError("unexpected shell")):
            result=bridge.run("2+2",certify=True,journal=lambda e,d:events.append(d))
        self.assertTrue(result["ok"])
        self.assertEqual(len(events),3)
        self.assertNotIn("must-never-run",json.dumps(events))

    def test_loopback_http_core_entry_with_fake_providers(self):
        import bazor_pc_relay_v3 as core
        events=[]
        with patch.object(core,"journal",side_effect=lambda e,d:events.append(d)), patch.object(core,"route_task",return_value={}), patch.object(bridge,"local_chat",side_effect=[self.reply("local-real"),self.reply("local-real",bridge.MARKER)]), patch.object(client,"chat",return_value=self.reply("external-real")):
            server=core.BazorHTTPServer(("127.0.0.1",0),core.ApiHandler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                req=urllib.request.Request("http://127.0.0.1:%d/api/v1/chat"%server.server_port,
                    data=json.dumps({"target":"mammouth_ollama","text":"2+2","bridge_e2e":True}).encode(),headers={"Content-Type":"application/json"})
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req,timeout=5) as response: result=json.load(response)
                self.assertTrue(result["ok"])
                self.assertEqual(result["answer"],bridge.MARKER)
                self.assertTrue(bridge.validate(result["bridge"],True))
            finally:
                server.shutdown();server.server_close();thread.join(2)


class WatcherRegressionTests(unittest.TestCase):
    def test_watcher_core_signatures_match(self):
        import hashlib
        import bazor_pc_relay_v3 as core
        path=Path(__file__).with_name("bazor_github_watcher.py")
        tree=ast.parse(path.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_expected_core_runtime_signature")
        scope={"os":os,"hashlib":hashlib,"ROOT":str(path.parent.parent)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),"exec"),scope)
        self.assertEqual(scope[fn.name](),core.CORE_RUNTIME_SIGNATURE)

    def test_filebus_rejects_path_traversal_and_unknown_provider(self):
        # Extract only the pure validation function: importing watcher starts its daemon.
        path=Path(__file__).with_name("bazor_github_watcher.py")
        source=ast.parse(path.read_text())
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=="_safe_filebus_message")
        import re
        scope={"os":os,"re":re,"ROOT":str(path.parent.parent)}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),"exec"),scope)
        for title in ("[bazor-filebus:ollama:../secret]", "[bazor-filebus:shell:test.md]", "[bazor-filebus:ollama:missing.md]"):
            with self.assertRaises(RuntimeError): scope["_safe_filebus_message"](title)


class RoomRegressionTests(unittest.TestCase):
    def test_existing_manual_room_routes(self):
        path=Path(__file__).resolve().parents[1]/"room-payload/v2.4/app/room_v2_server.py"
        spec=importlib.util.spec_from_file_location("bridge_room_test",path)
        room=importlib.util.module_from_spec(spec);spec.loader.exec_module(room)
        with patch.object(room,"engine_status",return_value={"ollama":{"available":True},"mammouth":{"available":False},"gpt":{"available":False}}):
            self.assertEqual(room.choose_route("simple")["selected"],"ollama")
            self.assertEqual(room.choose_route("simple","mammouth")["selected"],"mammouth")


if __name__ == "__main__":
    unittest.main(verbosity=2)
