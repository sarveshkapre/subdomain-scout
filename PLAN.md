# PLAN.md

## Pitch

Minimal, dependency-free subdomain discovery: wordlist → DNS resolve → NDJSON you can diff and pipeline.

## Features (current)

- Wordlist-based DNS resolution.
- NDJSON/JSONL output (one record per attempted subdomain).
- CLI via `python -m subdomain_scout` or `subdomain-scout`.

## Top risks / unknowns

- DNS resolution behavior varies by OS/resolver; results can differ across environments.
- Large wordlists can take time; needs careful concurrency + timeouts to avoid “hanging” lookups.
- False negatives: resolvers, caching, wildcard DNS, and network filtering can skew results.

## Commands

See `PROJECT.md` for the canonical commands:

- Setup: `make setup`
- Quality gate: `make check`
- Run: `python -m subdomain_scout --help`

## Shipped (latest run)

- Concurrent scanning (`--concurrency`) with safe, atomic output writes.
- `--out -` support for piping NDJSON to stdout.
- `--only-resolved` filtering, wordlist comment/blank-line handling, and per-record `error` field on resolver failures.
- `diff` command to compare two NDJSON runs for monitoring/CI.
- Best-effort wildcard DNS detection (`--detect-wildcard`) to reduce noisy “resolved” results.
- CDN-wildcard false-positive reduction via `--wildcard-threshold` and optional HTTP verification (`--wildcard-verify-http`).
- More flexible output filtering (`--status ...`) and retries for transient resolver failures.
- Machine-readable scan/diff summaries to stderr (`--summary-json`).
- Periodic scan progress updates to stderr (`scan --progress`).
- Wordlist input from stdin via `--wordlist -` for pipeline-friendly scans.
- CT ingestion command (`subdomain-scout ct`) backed by `crt.sh`.
- Optional CT label seeding for active scans via `scan --ct`.
- Scan observability upgrades: dedupe metrics in summary + per-record retry metadata (`attempts`, `retries`).
- Strict hostname validation for domains/labels to fail fast on malformed input.
- Optional takeover fingerprint checks during scans via `--takeover-check` with confidence scoring and custom catalog loading.
- Optional custom DNS resolver pinning via `scan --resolver` for more reproducible scans across environments.
- Resume/append scan mode via `scan --resume` to skip already-seen labels when writing to an existing output file.

## Next

- Expand takeover fingerprint coverage with false-positive guardrails.
- Improve wildcard DNS handling to reduce false positives (especially on CDN-backed domains where wildcard IPs overlap with real hosts).
- Add quiet/no-summary mode to better support machine-only pipeline execution.
