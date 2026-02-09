# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
- [ ] (P1) Add optional custom DNS resolver support (`--resolver`) for reproducible CI scans across environments.
- [ ] (P1) Add scan resume support (skip already-seen subdomains when appending outputs).
- [ ] (P1) Expand built-in takeover fingerprints and add false-positive guard tests per provider.
- [ ] (P2) Add benchmark fixture for large wordlists to track scan throughput regressions.
- [ ] (P2) Add release automation for semantic version bump + changelog cut.

## Implemented
- [x] (2026-02-09) Added takeover checks to `scan` with a versioned default fingerprint catalog and confidence scoring.
  - Evidence: `src/subdomain_scout/takeover.py`, `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`
- [x] (2026-02-09) Added takeover-focused test coverage for catalog loading, scoring, scanner integration, and CLI wiring.
  - Evidence: `tests/test_takeover.py`, `tests/test_scanner.py`, `tests/test_cli_takeover.py`
- [x] (2026-02-09) Added CLI/docs support for takeover controls (`--takeover-check`, timeout, custom catalog path) and summary metrics.
  - Evidence: `src/subdomain_scout/cli.py`, `README.md`, `PROJECT.md`, `PLAN.md`, `UPDATE.md`, `CHANGELOG.md`
- [x] (2026-02-09) Added structured run memory and incident-prevention docs.
  - Evidence: `PROJECT_MEMORY.md`, `INCIDENTS.md`
- [x] (2026-02-09) Verification evidence captured.
  - `make check` (pass; 29 tests)
  - `printf 'www\n' | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --summary-json --takeover-check --timeout 2 --takeover-timeout 2 --concurrency 1` (pass; `takeover_checked=1`)
- `tmp_fp=$(mktemp); cat > "$tmp_fp" <<'JSON'
{"version":"smoke-v1","fingerprints":[{"service":"SmokeService","body_substrings":["example domain"],"status_codes":[200]}]}
JSON
printf 'www\n' | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --summary-json --takeover-check --takeover-timeout 2 --takeover-fingerprints "$tmp_fp" --timeout 2 --concurrency 1; rm -f "$tmp_fp"` (pass; `takeover_suspected=1` smoke path)
- [x] (2026-02-09) Added CT ingestion via `crt.sh` with a dedicated `ct` CLI command and summary output.
  - Evidence: `src/subdomain_scout/ct.py`, `src/subdomain_scout/cli.py`, `tests/test_ct.py`, `tests/test_cli_ct.py`
- [x] (2026-02-09) Added `scan --ct` integration to merge passive CT-derived labels with active wordlist scanning.
  - Evidence: `src/subdomain_scout/cli.py`, `src/subdomain_scout/scanner.py`, `tests/test_cli_ct.py`
- [x] (2026-02-09) Added scan dedupe metrics and per-record retry metadata for observability.
  - Evidence: `src/subdomain_scout/scanner.py`, `tests/test_scanner.py`
- [x] (2026-02-09) Added strict hostname validation for domains and labels.
  - Evidence: `src/subdomain_scout/validation.py`, `tests/test_validation.py`
- [x] (2026-02-09) Verification evidence captured.
  - `make check` (pass; 22 tests)
  - `printf 'www\nwww\napi\n' | .venv/bin/python -m subdomain_scout scan --domain invalid.test --wordlist - --out - --summary-json --concurrency 1 --timeout 0.1` (pass)
  - `.venv/bin/python -m subdomain_scout ct --domain example.com --out - --limit 3 --timeout 30 --summary-json` (pass)
- [x] (2026-02-09) Pushed core feature commit and verified CI success.
  - Commit: `2d38df1`
  - GitHub Actions run: `21808091338` (success)
- [x] (2026-02-09) Documentation/tracker alignment commit pushed and CI-verified.
  - Commit: `c47e493`
  - GitHub Actions run: `21808109894` (success)

## Insights
- The highest product leverage at this stage is combining passive CT discovery with active DNS validation in one workflow (`scan --ct`), which materially improves discovery yield with minimal user overhead.
- Takeover signal checks are most useful when they run inline with active scans and emit per-record evidence/score that downstream automation can triage.
- Versioned fingerprint catalogs make detection behavior auditable and allow controlled custom overrides without code changes.
- Label deduplication is a low-risk performance win that reduces DNS calls and improves runtime determinism for repeated/merged sources.
- Retry count visibility (`attempts`/`retries`) is important for CI troubleshooting when resolvers are flaky but eventually succeed.

## Notes
- This file is maintained by the autonomous clone loop.
