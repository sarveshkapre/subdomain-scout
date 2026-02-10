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
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --only-resolved --resolver 1.1.1.1
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --only-resolved --resolver-file ./resolvers.txt
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --only-resolved --resolver 1.1.1.1 --include-cname
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --detect-wildcard --only-resolved
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --detect-wildcard --wildcard-verify-http --wildcard-threshold 3 --only-resolved
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --status resolved --status wildcard
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --summary-json
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --progress --progress-every 2
subdomain-scout scan --domain example.com --wordlist ./words.txt --out subdomains.jsonl --resume
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --takeover-check --summary-json
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --takeover-check --takeover-fingerprints ./fingerprints.json --summary-json
subdomain-scout scan --domain example.com --wordlist ./words.txt --out - --ct --ct-limit 200 --summary-json
printf "www\napi\n" | subdomain-scout scan --domain example.com --wordlist - --out - --only-resolved
subdomain-scout ct --domain example.com --out - --limit 50 --summary-json
```

Each output line is a JSON object:

```json
{"subdomain":"www.example.com","ips":["93.184.216.34"],"status":"resolved","elapsed_ms":12,"attempts":1,"retries":0}
```

When `--include-cname` is enabled (requires custom resolver mode), records may include a `cnames` array (CNAME chain targets), and CNAME-only results are emitted as `status=cname`.

When `--takeover-check` is enabled and a fingerprint matches, records include a `takeover` object with `service`, `confidence`, `score`, and fingerprint evidence metadata.

Custom takeover catalogs are JSON files shaped like:

```json
{
  "version": "2026-02-10",
  "fingerprints": [
    {
      "service": "ProviderName",
      "body_substrings": ["known dangling hostname message"],
      "status_codes": [404]
    }
  ]
}
```

## Diff

Compare two runs (especially useful with `--only-resolved` output):

```bash
subdomain-scout diff --old old.jsonl --new new.jsonl --fail-on-changes
subdomain-scout diff --old old.jsonl --new new.jsonl --resolved-only --only added --only changed
subdomain-scout diff --old old.jsonl --new new.jsonl --summary-only --summary-json
```
