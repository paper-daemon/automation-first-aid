import json, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation_first_aid import doctor, retry_decision, validate_json

class TestFirstAid(unittest.TestCase):
    def test_retry_transient(self):
        self.assertEqual(retry_decision("connection reset by peer", 1)["decision"], "RETRY_WITH_BACKOFF")
    def test_retry_permanent(self):
        self.assertEqual(retry_decision("permission denied", 1)["decision"], "STOP_AND_FIX")
    def test_exit_zero_wins_over_error_words(self):
        self.assertEqual(retry_decision("connection reset but recovered", 0)["decision"], "NO_RETRY")
        self.assertEqual(retry_decision("timeout while polling, final result saved", 0)["decision"], "NO_RETRY")
        self.assertEqual(retry_decision("permission denied warning from optional probe", 0)["decision"], "NO_RETRY")
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
    def test_jsonl_error_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.jsonl"
            p.write_text("{\"a\":1}\n{bad}\n", encoding="utf-8")
            r = validate_json(str(p))
            self.assertFalse(r["ok"]); self.assertEqual(r["line"], 2)
if __name__ == "__main__": unittest.main()
