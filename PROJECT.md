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
```

## Example

```bash
python -m subdomain_scout scan --domain example.com --wordlist words.txt --out subdomains.jsonl
```
