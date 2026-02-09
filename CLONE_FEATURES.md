# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
- [ ] (P0) Add takeover signal checks with a versioned fingerprint set and confidence scoring.
- [ ] (P1) Add optional custom DNS resolvers (`--resolver`) for reproducible CI scans across environments.
- [ ] (P1) Add scan resume support (skip already-seen subdomains when appending outputs).
- [ ] (P2) Add benchmark fixture for large wordlists to track scan throughput regressions.
- [ ] (P2) Add release automation for semantic version bump + changelog cut.

## Implemented
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

## Insights
- The highest product leverage at this stage is combining passive CT discovery with active DNS validation in one workflow (`scan --ct`), which materially improves discovery yield with minimal user overhead.
- Label deduplication is a low-risk performance win that reduces DNS calls and improves runtime determinism for repeated/merged sources.
- Retry count visibility (`attempts`/`retries`) is important for CI troubleshooting when resolvers are flaky but eventually succeed.

## Notes
- This file is maintained by the autonomous clone loop.
