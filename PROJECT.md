# PROJECT.md

Exact commands for working in this repo.

## Setup

```bash
make setup
```

## Quality gate

```bash
make check
```

## Run

```bash
python -m subdomain_scout --help
subdomain-scout --help
```

## Example

```bash
python -m subdomain_scout scan --domain example.com --wordlist words.txt --out subdomains.jsonl
subdomain-scout scan --domain example.com --wordlist words.txt --out subdomains.jsonl --concurrency 20
subdomain-scout scan --domain example.com --wordlist words.txt --out - --detect-wildcard --only-resolved
subdomain-scout scan --domain example.com --wordlist words.txt --out - --summary-json
subdomain-scout diff --old subdomains-old.jsonl --new subdomains-new.jsonl --resolved-only --fail-on-changes
subdomain-scout diff --old subdomains-old.jsonl --new subdomains-new.jsonl --summary-only --summary-json
```
