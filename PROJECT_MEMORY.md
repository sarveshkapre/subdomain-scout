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
  - Improve wildcard DNS handling to reduce false positives (especially on multi-level wildcards).

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

### 2026-02-09 - Add resolver pinning and resume/append scan mode
- Decision: Added optional custom DNS resolver pinning (`scan --resolver`) backed by a minimal DNS client (A/AAAA), plus resume/append mode (`scan --resume`) to skip already-seen labels when writing to an existing output file.
- Why: Resolver pinning improves determinism across environments/CI, and resume unlocks practical long-running wordlist workflows without re-scanning already-emitted results.
- Evidence:
  - Code: `src/subdomain_scout/dns_client.py`, `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`
  - Tests: `tests/test_dns_client.py`, `tests/test_resume.py`, `tests/test_cli_scan.py`
  - Validation: `make check`; CLI smoke scans for `--resolver` and `--resume` paths.
- Commit: `dcccb2d`, `a4396bf`
- Confidence: high
- Trust label: verified-local
- Follow-ups:
  - Improve wildcard DNS handling to reduce false positives (especially on multi-level wildcards).
  - Expand built-in takeover fingerprints with false-positive guardrails.

### 2026-02-09 - Improve wildcard detection for multi-level labels
- Decision: Wildcard detection now probes per-suffix wildcards (e.g. treating `foo.dev.example.com` as subject to `*.dev.example.com`) and caches wildcard probe results.
- Why: CT and user-provided labels can include multi-level labels; without suffix-aware probing, multi-level wildcard zones produce noisy “resolved” output.
- Evidence:
  - Code: `src/subdomain_scout/scanner.py`
  - Tests: `tests/test_wildcard.py` (multi-level wildcard simulation)
  - Validation: `make check`
- Commit: `0e4395e`
- Confidence: high
- Trust label: verified-local
- Follow-ups:
  - Reduce wildcard false positives on CDN-backed domains where wildcard IPs overlap with real hosts.

### 2026-02-09 - Add resolver list file input
- Decision: Added `scan --resolver-file` to load resolver IP[:port] entries from a file (skip blanks/comments; dedupe; merge with `--resolver`).
- Why: Resolver list files are a baseline UX for repeatable, automation-friendly scans and reduce CLI friction vs repeating `--resolver`.
- Evidence:
  - Code: `src/subdomain_scout/cli.py`, `src/subdomain_scout/dns_client.py`
  - Tests: `tests/test_dns_client.py` (local UDP DNS server + resolver-file integration)
  - Docs: `README.md`, `PROJECT.md`, `UPDATE.md`, `CHANGELOG.md`
  - Validation: `make check`
- Commit: `66128ab`
- Confidence: high
- Trust label: verified-local

### 2026-02-09 - Single-source CLI version
- Decision: `subdomain-scout --version` is now sourced from the source checkout (`pyproject.toml`) with a metadata fallback for installed builds.
- Why: Avoids version drift between code and CLI output in editable installs and keeps `--version` accurate in production.
- Evidence:
  - Code: `src/subdomain_scout/version.py`, `src/subdomain_scout/cli.py`
  - Tests: `tests/test_cli_version.py`
  - Validation: `make check`; `.venv/bin/python -m subdomain_scout --version`
- Commit: `3bba7a6`
- Confidence: high
- Trust label: verified-local

## Verification Evidence

- `make check` (pass; 35 tests)
- `tmpdir=$(mktemp -d) && printf "www\n" > "$tmpdir/words.txt" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/words.txt" --out - --only-resolved --resolver 1.1.1.1 --timeout 2 --concurrency 1 --summary-json > "$tmpdir/out.txt" 2> "$tmpdir/summary.json" && cat "$tmpdir/out.txt" && cat "$tmpdir/summary.json" && rm -rf "$tmpdir"` (pass; `attempted=1 resolved=1`)
- `tmpdir=$(mktemp -d) && printf "www\n" > "$tmpdir/w1.txt" && printf "www\ndoesnotexist\n" > "$tmpdir/w2.txt" && out="$tmpdir/out.jsonl" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/w1.txt" --out "$out" --timeout 2 --concurrency 1 --summary-json 2> "$tmpdir/s1.json" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/w2.txt" --out "$out" --timeout 2 --concurrency 1 --resume --summary-json 2> "$tmpdir/s2.json" && cat "$tmpdir/s1.json" && cat "$tmpdir/s2.json" && wc -l "$out" && tail -n 2 "$out" && rm -rf "$tmpdir"` (pass; second run `labels_skipped_existing=1`, output appended)
- `make check` (pass; 40 tests)
- `.venv/bin/python -m subdomain_scout --version` (pass; `0.1.1`)
- `printf "www\napi\n" | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --only-resolved --concurrency 1 --timeout 2 --summary-json` (pass; `attempted=2 resolved=1 wrote=1`)

## Mistakes And Fixes

### 2026-02-09 - Editable install version drift in `--version`
- Root cause: `importlib.metadata.version()` returns the version recorded at install time; editable installs don’t automatically refresh metadata when `pyproject.toml` changes.
- Fix: Prefer parsing `pyproject.toml` when present (source checkout), with metadata as a fallback for installed builds.
- Prevention rule: Keep `tests/test_cli_version.py` to guard `--version` against drift.
