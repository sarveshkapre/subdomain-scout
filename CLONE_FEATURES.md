# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
- [ ] (P2) Expand built-in takeover fingerprints and add false-positive guard tests per provider. [impact:3 effort:3 fit:4 diff:3 risk:2 conf:3]
- [ ] (P3) Add optional DNS record enrichment for resolved hosts (CNAME collection behind a flag). [impact:2 effort:3 fit:3 diff:2 risk:2 conf:2]
- [ ] (P3) Add a benchmark fixture for large wordlists to track scan throughput regressions. [impact:2 effort:3 fit:3 diff:1 risk:1 conf:3]
- [ ] (P3) Add release automation for semantic version bump + changelog cut. [impact:2 effort:3 fit:3 diff:1 risk:2 conf:3]
- [ ] (P3) Add `scan --hosts` mode to accept full hostnames (one per line) in addition to label+domain composition. [impact:2 effort:3 fit:3 diff:1 risk:2 conf:3]

## Implemented
- [x] (2026-02-09) Reduce wildcard false positives on CDN-backed domains via `--wildcard-threshold` and optional HTTP verification (`--wildcard-verify-http`).
  - Evidence: `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`, `tests/test_wildcard.py`, `README.md`, `PROJECT.md`, `CHANGELOG.md`
  - Commit: `f8c6eff`
  - CI: `21836755911` (success)
- [x] (2026-02-09) Add `scan --progress` and add `schema_version` to JSON summary payloads (`scan/ct/diff --summary-json`).
  - Evidence: `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`, `tests/test_cli_scan.py`, `tests/test_cli_ct.py`, `tests/test_cli_diff.py`, `README.md`, `PROJECT.md`, `CHANGELOG.md`
  - Commit: `5919514`, `82d5f45`
  - CI: `21836850508` (success), `21836942795` (success)
- [x] (2026-02-09) Improved wildcard detection for multi-level labels by probing per-suffix wildcards (e.g. `*.dev.example.com`) and caching results.
  - Evidence: `src/subdomain_scout/scanner.py`, `tests/test_wildcard.py`, `CHANGELOG.md`
  - Commit: `0e4395e`
  - CI: `21827776075` (failed ruff formatting; fixed in subsequent commit)
- [x] (2026-02-09) Added resolver list file support via `scan --resolver-file` (skip blanks/comments; dedupe) and documented it.
  - Evidence: `src/subdomain_scout/cli.py`, `src/subdomain_scout/dns_client.py`, `tests/test_dns_client.py`, `README.md`, `PROJECT.md`, `UPDATE.md`, `CHANGELOG.md`
  - Commit: `66128ab`
  - CI: `21827852953` (success)
- [x] (2026-02-09) Single-sourced CLI `--version` from the source checkout (`pyproject.toml`) with a metadata fallback for installed builds, plus a guard test.
  - Evidence: `src/subdomain_scout/version.py`, `src/subdomain_scout/cli.py`, `tests/test_cli_version.py`
  - Commit: `3bba7a6`
  - CI: `21827917275` (success)
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
- [x] (2026-02-09) Verification evidence captured.
  - `make check` (pass; 40 tests)
  - `.venv/bin/python -m subdomain_scout --version` (pass; `0.1.1`)
  - `printf "www\napi\n" | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --only-resolved --concurrency 1 --timeout 2 --summary-json` (pass; `attempted=2 resolved=1 wrote=1`)
  - CI: `21828058446` (success; head `65f8564`)

## Insights
- The highest product leverage at this stage is combining passive CT discovery with active DNS validation in one workflow (`scan --ct`), which materially improves discovery yield with minimal user overhead.
- Takeover signal checks are most useful when they run inline with active scans and emit per-record evidence/score that downstream automation can triage.
- Versioned fingerprint catalogs make detection behavior auditable and allow controlled custom overrides without code changes.
- Label deduplication is a low-risk performance win that reduces DNS calls and improves runtime determinism for repeated/merged sources.
- Retry count visibility (`attempts`/`retries`) is important for CI troubleshooting when resolvers are flaky but eventually succeed.
- Market scan notes (untrusted):
  - Resolver lists and resume are baseline UX (e.g., ProjectDiscovery `dnsx` has `-r` resolver list input and `-resume`). Sources: https://docs.projectdiscovery.io/opensource/dnsx/usage and https://github.com/projectdiscovery/dnsx
  - Wildcard handling often uses threshold-style heuristics (e.g., `dnsx` has `-wildcard-threshold`, default 5). Source: https://docs.projectdiscovery.io/opensource/dnsx/usage
  - Tools like `puredns` emphasize wildcard filtering as a core feature and use resolver list files by default. Source: https://github.com/d3mondev/puredns
  - Tools like `shuffledns` describe "smart wildcard elimination" using a per-IP thresholding heuristic. Source: https://github.com/projectdiscovery/shuffledns
  - Amass exposes resolver configuration for controlling DNS behavior across runs. Source: https://github.com/OWASP/Amass/wiki/The-Configuration-File

## Notes
- This file is maintained by the autonomous clone loop.
