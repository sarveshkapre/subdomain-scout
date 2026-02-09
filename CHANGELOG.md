# CHANGELOG

## v0.1.1 - Unreleased

- Add concurrent scanning (`--concurrency`) and `--only-resolved` output filtering.
- Support writing NDJSON to stdout via `--out -`.
- Add `diff` command to compare two JSONL/NDJSON runs (`subdomain-scout diff`).
- Add best-effort wildcard DNS detection (`--detect-wildcard`) and mark matching records as `status=wildcard`.
- Add flexible scan output filtering via `--status` and retry on transient DNS errors (`--retries`).
- Add machine-readable summaries to stderr via `--summary-json` for `scan` and `diff`.
- Allow `--wordlist -` to read labels from stdin for pipeline-friendly scans.
- Improve robustness: ignore blank/commented wordlist lines, atomic output writes, and include `error` field on resolver failures.
- Add `ct` command for certificate transparency ingestion via `crt.sh` with JSON summary support.
- Add `scan --ct` to merge CT-derived labels into active DNS scans.
- Add scan dedupe metrics (`labels_total`, `labels_unique`, `labels_deduped`, `ct_labels`) in summaries.
- Add per-record retry metadata in scan output (`attempts`, `retries`).
- Add strict domain/label validation to fail fast on malformed hostnames.

## v0.1.0 - 2026-01-31

- Wordlist-based DNS resolution with JSONL output.
