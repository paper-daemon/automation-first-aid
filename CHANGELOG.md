# Changelog

## 1.1.0
- Add `--strict-exit` so CI and monitoring can receive exit code 1 for actionable diagnostic failures.
- Keep transient `RETRY_WITH_BACKOFF` outcomes non-failing in strict mode while `STOP_AND_FIX` and `REVIEW` fail.
- Harden malformed URL handling so invalid port syntax is reported safely rather than crashing the display path.
- Redact URL userinfo and token/secret/password/API-key/signature-like query values in diagnostic output while leaving the actual request target unchanged.
- Add regression coverage for strict exit behavior, retry policy, malformed URLs, signed URLs, and strict JSON validation.
- Expand English-first operational documentation and CI examples.

## 1.0.0 - 2026-08-29
- Environment, disk-space, and optional network diagnostics.
- Retry-safety classification from error text and exit status.
- JSON / JSONL failure-position checks.
- Linux `systemd --user` diagnostics.
- JSON output mode.
