# Update (2026-02-09)

## Shipped

- Faster scans via concurrency (`--concurrency`).
- NDJSON piping support (`--out -`) with scan summary printed to stderr.
- Output filtering (`--only-resolved`) + more robust wordlist parsing (skip blanks/comments).
- More reliable writes (atomic temp file + rename) and optional per-record `error` field for resolver failures.
- `diff` command for comparing two runs (`subdomain-scout diff`).
- Best-effort wildcard DNS detection (`--detect-wildcard`).
- More flexible scan output filtering (`--status ...`) and retries for transient DNS errors (`--retries`).
- Machine-readable summaries to stderr via `--summary-json` (for CI/pipelines).
- Accept stdin wordlists via `--wordlist -`.
- Add certificate transparency ingestion command (`subdomain-scout ct`) via `crt.sh`.
- Add `scan --ct` / `--ct-limit` / `--ct-timeout` to merge passive CT labels into active scans.
- Improve scan observability with dedupe summary metrics and per-record retry metadata.
- Add strict domain/label validation for safer CLI input handling.
- Add optional takeover fingerprint checks during scans (`--takeover-check`) with confidence scoring and custom catalog support.

## How to try it

```bash
make setup
make check
subdomain-scout scan --domain example.com --wordlist words.txt --out subdomains.jsonl --concurrency 20
subdomain-scout scan --domain example.com --wordlist words.txt --out - --only-resolved
subdomain-scout scan --domain example.com --wordlist words.txt --out - --takeover-check --summary-json
subdomain-scout scan --domain example.com --wordlist words.txt --out - --ct --ct-limit 200 --summary-json
subdomain-scout ct --domain example.com --out - --limit 50 --summary-json
subdomain-scout diff --old old.jsonl --new new.jsonl --resolved-only --fail-on-changes
```

## PR

- No PR: changes landed directly on `main`.
