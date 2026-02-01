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

## Next

- Add `diff` command to compare two NDJSON runs (new/removed/resolved) for CI-friendly monitoring.
- Add optional wildcard-dns detection (best-effort heuristic) to reduce noisy “resolved” results.
