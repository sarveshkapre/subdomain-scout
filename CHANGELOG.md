# CHANGELOG

## v0.1.1 - Unreleased

- Add concurrent scanning (`--concurrency`) and `--only-resolved` output filtering.
- Support writing NDJSON to stdout via `--out -`.
- Add `diff` command to compare two JSONL/NDJSON runs (`subdomain-scout diff`).
- Add best-effort wildcard DNS detection (`--detect-wildcard`) and mark matching records as `status=wildcard`.
- Improve robustness: ignore blank/commented wordlist lines, atomic output writes, and include `error` field on resolver failures.

## v0.1.0 - 2026-01-31

- Wordlist-based DNS resolution with JSONL output.
