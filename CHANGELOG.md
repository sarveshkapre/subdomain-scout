# CHANGELOG

## v0.1.1 - Unreleased

- Add concurrent scanning (`--concurrency`) and `--only-resolved` output filtering.
- Support writing NDJSON to stdout via `--out -`.
- Add `diff` command to compare two JSONL/NDJSON runs (`subdomain-scout diff`).
- Add best-effort wildcard DNS detection (`--detect-wildcard`) and mark matching records as `status=wildcard`.
- Improve wildcard detection for multi-level labels by probing per-suffix wildcards (e.g. `*.dev.example.com`).
- Add flexible scan output filtering via `--status` and retry on transient DNS errors (`--retries`).
- Add machine-readable summaries to stderr via `--summary-json` for `scan` and `diff`.
- Allow `--wordlist -` to read labels from stdin for pipeline-friendly scans.
- Improve robustness: ignore blank/commented wordlist lines, atomic output writes, and include `error` field on resolver failures.
- Add `ct` command for certificate transparency ingestion via `crt.sh` with JSON summary support.
- Add `scan --ct` to merge CT-derived labels into active DNS scans.
- Add scan dedupe metrics (`labels_total`, `labels_unique`, `labels_deduped`, `ct_labels`) in summaries.
- Add per-record retry metadata in scan output (`attempts`, `retries`).
- Add optional custom DNS resolver pinning via `scan --resolver`.
- Add resume/append scan mode via `scan --resume` (skip already-seen labels when writing to an existing output file).
- Add strict domain/label validation to fail fast on malformed hostnames.
- Add optional takeover checks during scans (`--takeover-check`) using a versioned fingerprint catalog with confidence scoring and custom catalog override support.

## v0.1.0 - 2026-01-31

- Wordlist-based DNS resolution with JSONL output.
