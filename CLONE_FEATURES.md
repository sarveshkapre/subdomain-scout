# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
- [ ] (P1) (Selected) Improve wildcard DNS handling for multi-level labels (detect wildcard at each suffix like `*.dev.example.com`), with caching and tests. [impact:5 effort:3 fit:5 diff:3 risk:2 conf:4]
- [ ] (P2) (Selected) Add `scan --resolver-file` to load resolver IP[:port] entries from a file (skip blanks/comments; repeatable with `--resolver`). [impact:4 effort:2 fit:5 diff:2 risk:1 conf:4]
- [ ] (P2) (Selected) Single-source CLI `--version` from package metadata (avoid drift vs `pyproject.toml`) and add a guard test. [impact:3 effort:1 fit:4 diff:1 risk:1 conf:5]
- [ ] (P2) Expand built-in takeover fingerprints and add false-positive guard tests per provider. [impact:3 effort:3 fit:4 diff:3 risk:2 conf:3]
- [ ] (P3) Add output schema versioning: include a `schema_version` in summaries and document stability expectations. [impact:3 effort:2 fit:4 diff:2 risk:2 conf:3]
- [ ] (P3) Add a `scan --progress` option to print periodic progress/stats to stderr for long runs. [impact:3 effort:2 fit:3 diff:1 risk:1 conf:3]
- [ ] (P3) Add optional DNS record enrichment for resolved hosts (CNAME collection behind a flag). [impact:2 effort:3 fit:3 diff:2 risk:2 conf:2]
- [ ] (P3) Add a benchmark fixture for large wordlists to track scan throughput regressions. [impact:2 effort:3 fit:3 diff:1 risk:1 conf:3]
- [ ] (P3) Add release automation for semantic version bump + changelog cut. [impact:2 effort:3 fit:3 diff:1 risk:2 conf:3]
- [ ] (P3) Add `scan --hosts` mode to accept full hostnames (one per line) in addition to label+domain composition. [impact:2 effort:3 fit:3 diff:1 risk:2 conf:3]

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
- [x] (2026-02-09) Pushed takeover feature implementation and verified CI success.
  - Commit: `3eb6506`
  - GitHub Actions run: `21809865029` (success)
- [x] (2026-02-09) Pushed documentation/tracker sync commit and verified CI success.
  - Commit: `73d9b93`
  - GitHub Actions run: `21809876036` (success)
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
- [x] (2026-02-09) Added optional custom DNS resolver pinning via `scan --resolver` using a minimal UDP/TCP DNS client (A/AAAA) for reproducible CI scans.
  - Evidence: `src/subdomain_scout/dns_client.py`, `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`, `tests/test_dns_client.py`
  - Commit: `dcccb2d`
- [x] (2026-02-09) Added resume/append scan mode via `scan --resume` (skip already-seen labels when writing to an existing output file) and exposed `labels_skipped_existing` in summaries.
  - Evidence: `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`, `tests/test_resume.py`, `tests/test_cli_scan.py`
  - Commit: `a4396bf`
- [x] (2026-02-09) Updated docs and trackers to reflect `--resolver` and `--resume` behavior.
  - Evidence: `README.md`, `PROJECT.md`, `PLAN.md`, `ROADMAP.md`, `CHANGELOG.md`, `UPDATE.md`, `CLONE_FEATURES.md`, `PROJECT_MEMORY.md`
  - Commit: `81dfc45`
- [x] (2026-02-09) Verified CI success for tracker sync commit.
  - Commit: `425d9e5`
  - GitHub Actions run: `21820190782` (success)
- [x] (2026-02-09) Verified CI success for follow-up feature-tracker CI logging commit.
  - Commit: `6bc20a0`
  - GitHub Actions run: `21820220535` (success)

## Insights
- The highest product leverage at this stage is combining passive CT discovery with active DNS validation in one workflow (`scan --ct`), which materially improves discovery yield with minimal user overhead.
- Takeover signal checks are most useful when they run inline with active scans and emit per-record evidence/score that downstream automation can triage.
- Versioned fingerprint catalogs make detection behavior auditable and allow controlled custom overrides without code changes.
- Label deduplication is a low-risk performance win that reduces DNS calls and improves runtime determinism for repeated/merged sources.
- Retry count visibility (`attempts`/`retries`) is important for CI troubleshooting when resolvers are flaky but eventually succeed.
- Market scan notes (untrusted):
  - Many subdomain/DNS tools treat custom resolver lists and resume as baseline UX for stable automation (e.g., ProjectDiscovery `dnsx` has `-r` resolver list and `-resume`). Sources: https://docs.projectdiscovery.io/opensource/dnsx/usage and https://github.com/projectdiscovery/dnsx
  - Amass exposes resolver configuration for controlling DNS behavior across runs. Source: https://github.com/OWASP/Amass/wiki/The-Configuration-File

## Notes
- This file is maintained by the autonomous clone loop.
