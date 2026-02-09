# ROADMAP

## v0.1.0

- Wordlist DNS scan with JSONL output.

## v0.1.1

- Concurrent scanning, stdout output, output filtering, run diffs, and wildcard detection.

## v0.1.2

- CT log ingestion command (`subdomain-scout ct`) via `crt.sh`.
- Optional CT seeding for active scans (`scan --ct`).
- Label dedupe metrics and retry metadata in scan output.
- Optional takeover signal checks with a versioned fingerprint catalog and confidence scoring.

## Next

- Improve wildcard DNS handling to reduce false positives (especially on multi-level wildcards).
- Expand takeover fingerprint coverage with false-positive guardrails.
