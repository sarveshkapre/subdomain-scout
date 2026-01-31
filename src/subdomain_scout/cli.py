from __future__ import annotations

import argparse
from pathlib import Path

from .scanner import scan_domains


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subdomain-scout")
    parser.add_argument("--version", action="version", version="0.1.0")

    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="Scan subdomains from wordlist")
    p_scan.add_argument("--domain", required=True)
    p_scan.add_argument("--wordlist", required=True)
    p_scan.add_argument("--out", default="subdomains.jsonl")
    p_scan.add_argument("--timeout", type=float, default=3.0)
    p_scan.set_defaults(func=_run_scan)

    args = parser.parse_args(argv)
    return int(args.func(args))


def _run_scan(args: argparse.Namespace) -> int:
    return scan_domains(
        domain=args.domain,
        wordlist=Path(args.wordlist),
        out_path=Path(args.out),
        timeout=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
