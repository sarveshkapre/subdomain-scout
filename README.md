# Subdomain Scout

Minimal, dependency-free DNS wordlist-based subdomain discovery.

## Scope (v0.1.x)

- Wordlist → DNS resolve (concurrent).
- NDJSON/JSONL output (optionally to stdout).

## Quickstart

```bash
make setup
make check
```

## Usage

```bash
subdomain-scout scan --domain example.com --wordlist ./words.txt --out subdomains.jsonl
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --only-resolved
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --detect-wildcard --only-resolved
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --status resolved --status wildcard
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --summary-json
printf "www\napi\n" | subdomain-scout scan --domain example.com --wordlist - --out - --only-resolved
```

Each output line is a JSON object:

```json
{"subdomain":"www.example.com","ips":["93.184.216.34"],"status":"resolved","elapsed_ms":12}
```

## Diff

Compare two runs (especially useful with `--only-resolved` output):

```bash
subdomain-scout diff --old old.jsonl --new new.jsonl --fail-on-changes
subdomain-scout diff --old old.jsonl --new new.jsonl --resolved-only --only added --only changed
subdomain-scout diff --old old.jsonl --new new.jsonl --summary-only --summary-json
```
