# Automation First Aid 🧰

**Dependency-free first-response diagnostics for broken automations.**

Automation First Aid is a small Python CLI for the first 10 minutes after a workflow, worker, API integration, or local automation starts behaving strangely. It helps answer four questions quickly: Is the environment healthy? Is the input JSON valid? Is the failure safe to retry? Is the Linux user service actually running?

> 日本語: 自動化がコケた時の最初の切り分けを、設定変更なしで行う無料CLIです。Python 3.10+、外部依存なし。

![Automation First Aid cover](assets/cover.png)

## Quick start

```bash
python3 automation_first_aid.py doctor
python3 automation_first_aid.py doctor --network --url https://example.com
python3 automation_first_aid.py retry --text "connection reset by peer" --exit-code 1
python3 automation_first_aid.py jsoncheck logs.jsonl
python3 automation_first_aid.py systemd-user --unit my-worker.service
```

Use JSON output for another tool or monitor:

```bash
python3 automation_first_aid.py --json doctor
```

## CI / monitoring mode

By default the CLI is diagnostic and exits successfully after printing its result. Add `--strict-exit` when another process needs a stable failure signal:

```bash
python3 automation_first_aid.py --strict-exit jsoncheck payload.jsonl
python3 automation_first_aid.py --strict-exit doctor --network --url https://example.com/health
python3 automation_first_aid.py --strict-exit retry --text "permission denied" --exit-code 1
```

With `--strict-exit`, exit code `1` is returned when:

- a `doctor` or `systemd-user` check is NG;
- `jsoncheck` finds invalid JSON / JSONL;
- `retry` returns `STOP_AND_FIX` or `REVIEW`.

A transient failure classified as `RETRY_WITH_BACKOFF` does **not** fail strict mode. The tool reports that retry is a reasonable next action instead of pretending the underlying system is permanently broken.

## Commands

### `doctor`
Checks:

- Python 3.10+;
- target path existence and write access;
- at least 1 GiB free disk space;
- optional DNS resolution;
- optional HTTP(S) endpoint response;
- Linux `systemd --user` manager health when available.

HEAD requests fall back to GET only when the endpoint rejects HEAD with 403, 405, or 501. A real 404 remains a failure.

### `retry`
Classifies an observed error into:

- `NO_RETRY` — the process already exited successfully;
- `RETRY_WITH_BACKOFF` — transient/network/resource-like failure;
- `STOP_AND_FIX` — permanent/configuration-like failure;
- `REVIEW` — unknown failure that should be inspected before retrying.

A successful exit code wins over stale error words in logs. This helps avoid repeating an external effect just because an earlier attempt emitted a scary line. See [`docs/retry-success-boundary.md`](docs/retry-success-boundary.md).

### `jsoncheck`
Validates JSON or JSONL and reports the failing line/column where possible. Non-standard numeric constants such as `NaN`, `Infinity`, and `-Infinity` are rejected.

### `systemd-user`
Checks the Linux user manager and, optionally, whether a specific user unit is active and enabled.

## Safety boundaries

Automation First Aid is deliberately **diagnostic-only**.

It does not:

- restart services;
- rewrite configuration;
- repair files;
- delete data;
- automatically replay failed external actions.

That boundary is intentional. The tool should make the next decision safer, not create a second incident while diagnosing the first.

## URL privacy

When URL diagnostics are used, the real request URL is left unchanged but the displayed/logged URL is sanitized:

- username/password userinfo is redacted;
- token, secret, password, API-key, authorization, cookie, credential, signature and similar query values are redacted;
- malformed port syntax is rendered as `<invalid-url>` instead of leaking or crashing the diagnostic path.

## Example CI step

```yaml
- name: Validate generated JSONL
  run: python automation_first_aid.py --strict-exit jsoncheck build/events.jsonl

- name: Probe service health
  run: python automation_first_aid.py --strict-exit doctor --network --url https://example.com/health
```

## Test suite

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Regression coverage includes retry classification, successful-final-state precedence, HEAD→GET fallback boundaries, credential-safe URL display, malformed URLs, strict JSON validation, and strict process-exit behavior.

## Good fits

- n8n / Zapier / Make-style workflow support
- long-running workers and scheduled jobs
- webhook and API integration diagnostics
- JSON/JSONL content pipelines
- Linux user-service triage
- preflight checks before an automated retry loop

## Distribution

- GitHub: https://github.com/paper-daemon/automation-first-aid
- BOOTH: https://amase-memo.booth.pm/items/8778532
- Release: https://github.com/paper-daemon/automation-first-aid/releases/tag/v1.0.0
- Builder portfolio: https://paper-daemon.github.io/global.html

Python 3.10+ / standard library only / MIT License.
