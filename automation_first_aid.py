#!/usr/bin/env python3
"""Automation First Aid - dependency-free troubleshooting CLI."""
from __future__ import annotations
import argparse, json, os, platform, shutil, socket, subprocess, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

RETRYABLE = (
    "timeout", "timed out", "temporarily unavailable", "connection reset",
    "connection refused", "rate limit", "too many requests", "502", "503", "504",
    "network is unreachable", "try again", "econnreset", "etimedout",
)
PERMANENT = (
    "permission denied", "unauthorized", "forbidden", "invalid token", "bad credentials",
    "not found", "no such file", "syntax error", "invalid argument", "unsupported",
)

def result(name: str, ok: bool, detail: str) -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}

def doctor(path: str, url: str | None, network: bool) -> list[dict]:
    out = []
    p = Path(path).expanduser().resolve()
    out.append(result("python", sys.version_info >= (3, 10), platform.python_version()))
    out.append(result("path_exists", p.exists(), str(p)))
    if p.exists():
        out.append(result("path_writable", os.access(p, os.W_OK), str(p)))
        usage = shutil.disk_usage(p)
        free_gib = usage.free / (1024**3)
        out.append(result("disk_free", free_gib >= 1.0, f"{free_gib:.2f} GiB free"))
    if network:
        try:
            socket.getaddrinfo("github.com", 443)
            out.append(result("dns", True, "github.com resolved"))
        except OSError as e:
            out.append(result("dns", False, str(e)))
    if url:
        try:
            req = Request(url, method="HEAD", headers={"User-Agent": "Automation-First-Aid/1.0"})
            with urlopen(req, timeout=8) as r:
                out.append(result("url", 200 <= r.status < 400, f"HTTP {r.status} {url}"))
        except HTTPError as e:
            code = e.code
            e.close()
            if code in {405, 501}:
                try:
                    req = Request(url, method="GET", headers={"User-Agent": "Automation-First-Aid/1.0"})
                    with urlopen(req, timeout=8) as r:
                        out.append(result("url", 200 <= r.status < 400, f"HTTP {r.status} {url} (GET fallback after HEAD {code})"))
                except HTTPError as ge:
                    get_code = ge.code
                    ge.close()
                    out.append(result("url", False, f"HTTP {get_code} {url} (GET fallback after HEAD {code})"))
                except URLError as ge:
                    out.append(result("url", False, f"{url}: {ge.reason} (GET fallback after HEAD {code})"))
            else:
                out.append(result("url", False, f"HTTP {code} {url}"))
        except URLError as e:
            out.append(result("url", False, f"{url}: {e.reason}"))
    if sys.platform.startswith("linux") and shutil.which("systemctl"):
        cp = subprocess.run(["systemctl", "--user", "is-system-running"], text=True, capture_output=True, timeout=5)
        state = (cp.stdout or cp.stderr).strip() or f"exit={cp.returncode}"
        connected = "failed to connect" not in state.lower() and "no medium found" not in state.lower()
        out.append(result("systemd_user", connected and state.lower() in {"running", "degraded", "starting", "maintenance"}, state))
    return out

def retry_decision(text: str, exit_code: int | None) -> dict:
    if exit_code == 0:
        return {"decision": "NO_RETRY", "reason": "exit code is 0"}
    low = text.lower()
    if any(x in low for x in PERMANENT):
        return {"decision": "STOP_AND_FIX", "reason": "permanent/configuration-like error"}
    if any(x in low for x in RETRYABLE) or exit_code in (75, 111, 124, 137, 143):
        return {"decision": "RETRY_WITH_BACKOFF", "reason": "transient/network/resource-like error"}
    return {"decision": "REVIEW", "reason": "unknown failure; inspect before retrying"}


def _reject_json_constant(value: str):
    raise ValueError(f"non-standard JSON numeric constant: {value}")

def strict_json_loads(text: str):
    return json.loads(text, parse_constant=_reject_json_constant)

def validate_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "path": str(p), "error": "file not found"}
    if p.suffix.lower() == ".jsonl":
        good = 0
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                strict_json_loads(line)
                good += 1
            except json.JSONDecodeError as e:
                return {"ok": False, "path": str(p), "line": n, "column": e.colno, "error": e.msg, "good_lines": good}
            except ValueError as e:
                return {"ok": False, "path": str(p), "line": n, "error": str(e), "good_lines": good}
        return {"ok": True, "path": str(p), "valid_lines": good, "format": "jsonl"}
    try:
        obj = strict_json_loads(p.read_text(encoding="utf-8"))
        return {"ok": True, "path": str(p), "format": "json", "type": type(obj).__name__}
    except json.JSONDecodeError as e:
        return {"ok": False, "path": str(p), "line": e.lineno, "column": e.colno, "error": e.msg}
    except ValueError as e:
        return {"ok": False, "path": str(p), "error": str(e)}

def systemd_user(unit: str | None) -> list[dict]:
    if not sys.platform.startswith("linux") or not shutil.which("systemctl"):
        return [result("systemd_user", False, "systemctl not available on this OS")]
    cmds = [(["systemctl", "--user", "is-system-running"], "manager")]
    if unit:
        cmds += [
            (["systemctl", "--user", "is-active", unit], "unit_active"),
            (["systemctl", "--user", "is-enabled", unit], "unit_enabled"),
        ]
    out = []
    for cmd, name in cmds:
        try:
            cp = subprocess.run(cmd, text=True, capture_output=True, timeout=5)
            detail = (cp.stdout or cp.stderr).strip() or f"exit={cp.returncode}"
            out.append(result(name, cp.returncode == 0, detail))
        except Exception as e:
            out.append(result(name, False, str(e)))
    return out

def dump(data, as_json: bool):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    rows = data if isinstance(data, list) else [data]
    for row in rows:
        if "check" in row:
            status = "OK" if row["ok"] else "NG"
            print(f"[{status}] {row['check']}: {row['detail']}")
        else:
            print(" | ".join(f"{k}={v}" for k, v in row.items()))

def build_parser():
    p = argparse.ArgumentParser(prog="automation-first-aid", description="自動化トラブルの最初の切り分けを依存ゼロで。")
    p.add_argument("--json", action="store_true", help="JSONで出力")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="環境・ディスク・任意ネットワークを診断")
    d.add_argument("--path", default=".")
    d.add_argument("--network", action="store_true")
    d.add_argument("--url")
    r = sub.add_parser("retry", help="エラー文から再試行してよいか判定")
    r.add_argument("--text", required=True)
    r.add_argument("--exit-code", type=int)
    j = sub.add_parser("jsoncheck", help="JSON / JSONLの壊れた位置を表示")
    j.add_argument("path")
    s = sub.add_parser("systemd-user", help="systemd --user を診断")
    s.add_argument("--unit")
    return p

def main():
    args = build_parser().parse_args()
    if args.cmd == "doctor": data = doctor(args.path, args.url, args.network)
    elif args.cmd == "retry": data = retry_decision(args.text, args.exit_code)
    elif args.cmd == "jsoncheck": data = validate_json(args.path)
    else: data = systemd_user(args.unit)
    dump(data, args.json)

if __name__ == "__main__":
    main()
