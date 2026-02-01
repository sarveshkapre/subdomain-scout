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
```

Each output line is a JSON object:

```json
{"subdomain":"www.example.com","ips":["93.184.216.34"],"status":"resolved","elapsed_ms":12}
```
