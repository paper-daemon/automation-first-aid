import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation_first_aid import retry_decision, validate_json

class TestFirstAid(unittest.TestCase):
    def test_retry_transient(self):
        self.assertEqual(retry_decision("connection reset by peer", 1)["decision"], "RETRY_WITH_BACKOFF")
    def test_retry_permanent(self):
        self.assertEqual(retry_decision("permission denied", 1)["decision"], "STOP_AND_FIX")
    def test_jsonl_error_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.jsonl"
            p.write_text("{\"a\":1}\n{bad}\n", encoding="utf-8")
            r = validate_json(str(p))
            self.assertFalse(r["ok"]); self.assertEqual(r["line"], 2)
if __name__ == "__main__": unittest.main()
