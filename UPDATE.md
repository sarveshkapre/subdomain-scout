# Update (2026-02-01)

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

## How to try it

```bash
make setup
make check
subdomain-scout scan --domain example.com --wordlist words.txt --out subdomains.jsonl --concurrency 20
subdomain-scout scan --domain example.com --wordlist words.txt --out - --only-resolved
subdomain-scout diff --old old.jsonl --new new.jsonl --resolved-only --fail-on-changes
```

## PR

- No PR: changes landed directly on `main`.
