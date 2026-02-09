# PROJECT_MEMORY

Structured project memory for autonomous maintenance runs.

## Decisions

### 2026-02-09 - Add takeover fingerprint checks to active scans
- Decision: Added optional takeover probing in `scan` via `--takeover-check`, with versioned fingerprints, confidence scoring, and custom catalog loading.
- Why: This was the highest-impact open roadmap gap for production relevance; it surfaces likely dangling-service risk signals in the same workflow users already run.
- Evidence:
  - Code: `src/subdomain_scout/takeover.py`, `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`
  - Tests: `tests/test_takeover.py`, `tests/test_scanner.py`, `tests/test_cli_takeover.py`
  - Validation: `make check`; CLI smoke scans with and without custom fingerprint catalog.
- Commit: `3eb6506`
- Confidence: high
- Trust label: verified-local
- Follow-ups:
  - Expand built-in fingerprints with additional provider signatures and false-positive guardrails.
  - Add resolver pinning support for reproducible behavior across CI environments.

### 2026-02-09 - Synchronize docs and operational trackers with takeover behavior
- Decision: Updated product docs, roadmap/changelog, clone tracker, and run memory/incident files to match shipped CLI behavior and validation evidence.
- Why: Production-readiness depends on keeping operational docs aligned with current code and CI-traceable evidence.
- Evidence:
  - Docs: `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `PROJECT.md`, `PLAN.md`, `UPDATE.md`
  - Trackers: `CLONE_FEATURES.md`, `PROJECT_MEMORY.md`, `INCIDENTS.md`
  - CI: `https://github.com/sarveshkapre/subdomain-scout/actions/runs/21809876036`
- Commit: `73d9b93`
- Confidence: high
- Trust label: verified-local-and-ci
- Follow-ups:
  - Keep `PROJECT_MEMORY.md` as the canonical decision/evidence ledger for each future automation cycle.
