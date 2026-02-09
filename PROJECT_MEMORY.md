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

## Verification Evidence

- `make check` (pass; 35 tests)
- `tmpdir=$(mktemp -d) && printf "www\n" > "$tmpdir/words.txt" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/words.txt" --out - --only-resolved --resolver 1.1.1.1 --timeout 2 --concurrency 1 --summary-json > "$tmpdir/out.txt" 2> "$tmpdir/summary.json" && cat "$tmpdir/out.txt" && cat "$tmpdir/summary.json" && rm -rf "$tmpdir"` (pass; `attempted=1 resolved=1`)
- `tmpdir=$(mktemp -d) && printf "www\n" > "$tmpdir/w1.txt" && printf "www\ndoesnotexist\n" > "$tmpdir/w2.txt" && out="$tmpdir/out.jsonl" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/w1.txt" --out "$out" --timeout 2 --concurrency 1 --summary-json 2> "$tmpdir/s1.json" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/w2.txt" --out "$out" --timeout 2 --concurrency 1 --resume --summary-json 2> "$tmpdir/s2.json" && cat "$tmpdir/s1.json" && cat "$tmpdir/s2.json" && wc -l "$out" && tail -n 2 "$out" && rm -rf "$tmpdir"` (pass; second run `labels_skipped_existing=1`, output appended)
