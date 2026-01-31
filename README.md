# Subdomain Scout

Minimal DNS wordlist-based subdomain discovery.

## Scope (v0.1.0)

- Wordlist → DNS resolve.
- JSONL output.

## Quickstart

```bash
make setup
make check
```

## Usage

```bash
python -m subdomain_scout scan --domain example.com --wordlist ./words.txt --out subdomains.jsonl
```
