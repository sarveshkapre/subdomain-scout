# CHANGELOG

## v0.1.1 - Unreleased

- Add concurrent scanning (`--concurrency`) and `--only-resolved` output filtering.
- Support writing NDJSON to stdout via `--out -`.
- Improve robustness: ignore blank/commented wordlist lines, atomic output writes, and include `error` field on resolver failures.

## v0.1.0 - 2026-01-31

- Wordlist-based DNS resolution with JSONL output.
