# PROJECT_MEMORY

Structured project memory for autonomous maintenance runs.

## Decisions

### 2026-02-10 - Preserve CNAME metadata when annotating scan results
- Decision: Keep `cnames` intact when the scanner re-labels a result as `wildcard` or attaches a `takeover` object, by using `dataclasses.replace()` instead of reconstructing partial `Result` objects.
- Why: Reconstructing `Result` objects in the scanner dropped `cnames`, which made `--include-cname` output inconsistent (especially when `--takeover-check` or wildcard heuristics were enabled).
- Evidence:
  - Code: `src/subdomain_scout/scanner.py`
  - Tests: `tests/test_scanner.py` (`test_scan_takeover_checker_preserves_cnames`)
  - Validation: `make check`
- Commit: `b705613`
- Confidence: high
- Trust label: verified-local
- Follow-ups:
  - Consider adding a similar regression test for the wildcard re-label path when `cnames` are present.

### 2026-02-10 - Follow CNAME chains in custom resolver mode; emit CNAME metadata
- Decision: Custom resolver mode now follows CNAME chains when resolving A/AAAA, and `scan --include-cname` can emit observed CNAME chains (`cnames`) while classifying CNAME-only results as `status=cname`. `diff` comparisons now include `cnames` when present.
- Why: Resolver-pinned scans previously produced false negatives for CNAME-only names (NOERROR + CNAME + no A/AAAA in the immediate answer), and missing CNAME visibility makes triage and takeover workflows harder.
- Evidence:
  - Code: `src/subdomain_scout/dns_client.py`, `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`, `src/subdomain_scout/diff.py`
  - Tests: `tests/test_dns_client.py`, `tests/test_cli_diff.py`
  - Docs: `README.md`, `CHANGELOG.md`
  - Validation: `make check`; CLI smoke commands (see Verification Evidence)
  - CI: `https://github.com/sarveshkapre/subdomain-scout/actions/runs/21856831792`
- Commit: `54f3384`, `cca0145`
- Confidence: high
- Trust label: verified-local-and-ci
- Follow-ups:
  - Consider optional inclusion of the final canonical target hostname (when CNAME present) in addition to the chain for easier triage.

### 2026-02-09 - Reduce wildcard false positives with thresholding and HTTP verification
- Decision: Added `scan --detect-wildcard` refinements for CDN-backed domains via `--wildcard-threshold` and optional HTTP signature verification (`--wildcard-verify-http` / `--wildcard-http-timeout`).
- Why: Wildcard zones on CDNs can overlap IPs with real hosts, creating noisy `status=wildcard` false positives; HTTP comparison against a random wildcard probe is a pragmatic, dependency-free discriminator.
- Evidence:
  - Code: `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`
  - Tests: `tests/test_wildcard.py` (`test_scan_wildcard_http_verification_can_flip_false_positive`)
  - Docs: `README.md`, `PROJECT.md`, `CHANGELOG.md`
  - Validation: `make check`
  - CI: `https://github.com/sarveshkapre/subdomain-scout/actions/runs/21836755911`
- Commit: `f8c6eff`
- Confidence: high
- Trust label: verified-local-and-ci
- Follow-ups:
  - Consider optional CNAME enrichment to further disambiguate wildcard/CDN behavior without relying on HTTP.

### 2026-02-09 - Add scan progress and summary schema versioning
- Decision: Added `scan --progress` / `--progress-every` for periodic stderr progress, and added `schema_version=1` to `scan/ct/diff --summary-json` payloads.
- Why: Long-running scans benefit from operator feedback; explicit schema versioning makes downstream automation safer and future changes auditable.
- Evidence:
  - Code: `src/subdomain_scout/scanner.py`, `src/subdomain_scout/cli.py`
  - Tests: `tests/test_cli_scan.py`, `tests/test_cli_ct.py`, `tests/test_cli_diff.py`
  - Docs: `README.md`, `PROJECT.md`, `CHANGELOG.md`
  - Validation: `make check`; CLI smoke commands (see Verification Evidence)
  - CI: `https://github.com/sarveshkapre/subdomain-scout/actions/runs/21836850508`, `https://github.com/sarveshkapre/subdomain-scout/actions/runs/21836942795`
- Commit: `5919514`, `82d5f45`
- Confidence: high
- Trust label: verified-local-and-ci
- Follow-ups:
  - Consider a machine-readable progress mode (JSON progress lines) if automation wants both progress and `--summary-json`.

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

- `make check` (pass; 47 tests)
- `printf "www\n" | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --only-resolved --concurrency 1 --timeout 2 --summary-json` (pass)
- `printf "www\n" | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --only-resolved --resolver 1.1.1.1 --include-cname --concurrency 1 --timeout 2 --summary-json` (pass)
- `tmpdir=$(mktemp -d) && printf '{"subdomain":"a.example.com","status":"resolved","ips":["1.1.1.1"],"cnames":["old.example.com"]}'"\\n" > "$tmpdir/old.jsonl" && printf '{"subdomain":"a.example.com","status":"resolved","ips":["1.1.1.1"],"cnames":["new.example.com"]}'"\\n" > "$tmpdir/new.jsonl" && .venv/bin/python -m subdomain_scout diff --old "$tmpdir/old.jsonl" --new "$tmpdir/new.jsonl" --only changed && rm -rf "$tmpdir"` (pass)

- `make check` (pass; 42 tests)
- `printf "www\n" | .venv/bin/python -m subdomain_scout scan --domain invalid.test --wordlist - --out - --progress --progress-every 0 --timeout 0.1 --concurrency 1` (pass; includes `progress attempted=1` and `scanned attempted=1`)
- `printf "www\n" | .venv/bin/python -m subdomain_scout scan --domain invalid.test --wordlist - --out - --summary-json --timeout 0.1 --concurrency 1` (pass; `schema_version=1`)
- `tmpdir=$(mktemp -d) && printf '{"subdomain":"a.example.com","status":"resolved","ips":[]}'"\\n" > "$tmpdir/old.jsonl" && printf '{"subdomain":"a.example.com","status":"resolved","ips":[]}'"\\n"'{"subdomain":"b.example.com","status":"resolved","ips":["1.1.1.1"]}'"\\n" > "$tmpdir/new.jsonl" && .venv/bin/python -m subdomain_scout diff --old "$tmpdir/old.jsonl" --new "$tmpdir/new.jsonl" --summary-only --summary-json && rm -rf "$tmpdir"` (pass; `schema_version=1`)

- `make check` (pass; 35 tests)
- `tmpdir=$(mktemp -d) && printf "www\n" > "$tmpdir/words.txt" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/words.txt" --out - --only-resolved --resolver 1.1.1.1 --timeout 2 --concurrency 1 --summary-json > "$tmpdir/out.txt" 2> "$tmpdir/summary.json" && cat "$tmpdir/out.txt" && cat "$tmpdir/summary.json" && rm -rf "$tmpdir"` (pass; `attempted=1 resolved=1`)
- `tmpdir=$(mktemp -d) && printf "www\n" > "$tmpdir/w1.txt" && printf "www\ndoesnotexist\n" > "$tmpdir/w2.txt" && out="$tmpdir/out.jsonl" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/w1.txt" --out "$out" --timeout 2 --concurrency 1 --summary-json 2> "$tmpdir/s1.json" && .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist "$tmpdir/w2.txt" --out "$out" --timeout 2 --concurrency 1 --resume --summary-json 2> "$tmpdir/s2.json" && cat "$tmpdir/s1.json" && cat "$tmpdir/s2.json" && wc -l "$out" && tail -n 2 "$out" && rm -rf "$tmpdir"` (pass; second run `labels_skipped_existing=1`, output appended)
- `make check` (pass; 40 tests)
- `.venv/bin/python -m subdomain_scout --version` (pass; `0.1.1`)
- `printf "www\napi\n" | .venv/bin/python -m subdomain_scout scan --domain example.com --wordlist - --out - --only-resolved --concurrency 1 --timeout 2 --summary-json` (pass; `attempted=2 resolved=1 wrote=1`)

## Mistakes And Fixes

### 2026-02-09 - CI failed due to missed formatter run
- Root cause: Pushed a functional change without running the canonical gate (`make check`), so CI failed on `ruff format --check`.
- Fix: Ran `ruff format` and shipped the follow-up commit that included the formatting changes.
- Prevention rule: Always run `make check` locally before pushing to `main`.

### 2026-02-09 - Editable install version drift in `--version`
- Root cause: `importlib.metadata.version()` returns the version recorded at install time; editable installs don’t automatically refresh metadata when `pyproject.toml` changes.
- Fix: Prefer parsing `pyproject.toml` when present (source checkout), with metadata as a fallback for installed builds.
- Prevention rule: Keep `tests/test_cli_version.py` to guard `--version` against drift.
