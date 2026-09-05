import json, subprocess, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation_first_aid import doctor, retry_decision, validate_json, display_url, diagnostic_failed

class TestFirstAid(unittest.TestCase):
    def test_retry_transient(self):
        self.assertEqual(retry_decision("connection reset by peer", 1)["decision"], "RETRY_WITH_BACKOFF")

    def test_retry_permanent(self):
        self.assertEqual(retry_decision("permission denied", 1)["decision"], "STOP_AND_FIX")

    def test_exit_zero_wins_over_error_words(self):
        self.assertEqual(retry_decision("connection reset but recovered", 0)["decision"], "NO_RETRY")
        self.assertEqual(retry_decision("timeout while polling, final result saved", 0)["decision"], "NO_RETRY")
        self.assertEqual(retry_decision("permission denied warning from optional probe", 0)["decision"], "NO_RETRY")

    def test_diagnostic_failed_policy(self):
        self.assertFalse(diagnostic_failed("doctor", [{"ok": True}]))
        self.assertTrue(diagnostic_failed("doctor", [{"ok": True}, {"ok": False}]))
        self.assertFalse(diagnostic_failed("jsoncheck", {"ok": True}))
        self.assertTrue(diagnostic_failed("jsoncheck", {"ok": False}))
        self.assertFalse(diagnostic_failed("retry", {"decision": "RETRY_WITH_BACKOFF"}))
        self.assertFalse(diagnostic_failed("retry", {"decision": "NO_RETRY"}))
        self.assertTrue(diagnostic_failed("retry", {"decision": "STOP_AND_FIX"}))
        self.assertTrue(diagnostic_failed("retry", {"decision": "REVIEW"}))

    def test_strict_exit_cli_for_retry(self):
        cp = subprocess.run([
            sys.executable, "automation_first_aid.py", "--strict-exit", "retry",
            "--text", "permission denied", "--exit-code", "1"
        ], text=True, capture_output=True)
        self.assertEqual(cp.returncode, 1)
        self.assertIn("STOP_AND_FIX", cp.stdout)

        transient = subprocess.run([
            sys.executable, "automation_first_aid.py", "--strict-exit", "retry",
            "--text", "connection reset by peer", "--exit-code", "1"
        ], text=True, capture_output=True)
        self.assertEqual(transient.returncode, 0)
        self.assertIn("RETRY_WITH_BACKOFF", transient.stdout)

    def test_strict_exit_cli_for_jsoncheck(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"x":', encoding="utf-8")
            cp = subprocess.run([
                sys.executable, "automation_first_aid.py", "--strict-exit", "jsoncheck", str(p)
            ], text=True, capture_output=True)
            self.assertEqual(cp.returncode, 1)
            self.assertIn("ok=False", cp.stdout)

    def test_url_head_405_falls_back_to_get(self):
        class H(BaseHTTPRequestHandler):
            get_calls = 0
            def do_HEAD(self):
                self.send_response(405); self.end_headers()
            def do_GET(self):
                type(self).get_calls += 1
                self.send_response(200); self.end_headers()
            def log_message(self, *_): pass
        server = HTTPServer(("127.0.0.1", 0), H)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            rows = doctor(".", f"http://127.0.0.1:{server.server_port}/", False)
        finally:
            server.shutdown(); thread.join(timeout=2); server.server_close()
        row = next(x for x in rows if x["check"] == "url")
        self.assertTrue(row["ok"]); self.assertEqual(H.get_calls, 1)
        self.assertIn("GET fallback after HEAD 405", row["detail"])

    def test_url_head_403_falls_back_to_get(self):
        class H(BaseHTTPRequestHandler):
            get_calls = 0
            def do_HEAD(self):
                self.send_response(403); self.end_headers()
            def do_GET(self):
                type(self).get_calls += 1
                self.send_response(200); self.end_headers()
            def log_message(self, *_): pass
        server = HTTPServer(("127.0.0.1", 0), H)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            rows = doctor(".", f"http://127.0.0.1:{server.server_port}/", False)
        finally:
            server.shutdown(); thread.join(timeout=2); server.server_close()
        row = next(x for x in rows if x["check"] == "url")
        self.assertTrue(row["ok"]); self.assertEqual(H.get_calls, 1)
        self.assertIn("GET fallback after HEAD 403", row["detail"])

    def test_url_head_404_does_not_fall_back(self):
        class H(BaseHTTPRequestHandler):
            get_calls = 0
            def do_HEAD(self):
                self.send_response(404); self.end_headers()
            def do_GET(self):
                type(self).get_calls += 1
                self.send_response(200); self.end_headers()
            def log_message(self, *_): pass
        server = HTTPServer(("127.0.0.1", 0), H)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            rows = doctor(".", f"http://127.0.0.1:{server.server_port}/", False)
        finally:
            server.shutdown(); thread.join(timeout=2); server.server_close()
        row = next(x for x in rows if x["check"] == "url")
        self.assertFalse(row["ok"]); self.assertEqual(H.get_calls, 0)
        self.assertIn("HTTP 404", row["detail"])

    def test_display_url_redacts_userinfo_and_secret_query_values(self):
        safe = display_url("https://alice:supersecret@example.com/path?token=abc&mode=ro&X-Amz-Signature=signed")
        self.assertNotIn("alice", safe)
        self.assertNotIn("supersecret", safe)
        self.assertNotIn("token=abc", safe)
        self.assertNotIn("signed", safe)
        self.assertIn("%3Credacted%3E", safe)
        self.assertIn("mode=ro", safe)

    def test_display_url_handles_invalid_port_without_raising(self):
        self.assertEqual(display_url("https://example.com:notaport/?token=abc"), "<invalid-url>")

    def test_jsonl_error_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.jsonl"
            p.write_text("{\"a\":1}\n{bad}\n", encoding="utf-8")
            r = validate_json(str(p))
            self.assertFalse(r["ok"]); self.assertEqual(r["line"], 2)

    def test_non_standard_numeric_constants_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for token in ("NaN", "Infinity", "-Infinity"):
                p = Path(d) / "x.json"
                p.write_text('{"value": '+token+'}', encoding="utf-8")
                r = validate_json(str(p))
                self.assertFalse(r["ok"], token)
                self.assertIn("non-standard JSON numeric constant", r["error"])

    def test_jsonl_non_standard_numeric_constant_reports_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.jsonl"
            p.write_text('{"a":1}\n{"value":Infinity}\n', encoding="utf-8")
            r = validate_json(str(p))
            self.assertFalse(r["ok"]); self.assertEqual(r["line"], 2); self.assertEqual(r["good_lines"], 1)

if __name__ == "__main__": unittest.main()
