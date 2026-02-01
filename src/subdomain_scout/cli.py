from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scanner import scan_domains_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subdomain-scout")
    parser.add_argument("--version", action="version", version="0.1.1")

    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="Scan subdomains from wordlist")
    p_scan.add_argument("--domain", required=True)
    p_scan.add_argument("--wordlist", required=True)
    p_scan.add_argument(
        "--out",
        default="subdomains.jsonl",
        help="Output path (use '-' for stdout)",
    )
    p_scan.add_argument("--timeout", type=float, default=3.0)
    p_scan.add_argument("--concurrency", type=int, default=20)
    p_scan.add_argument(
        "--only-resolved",
        action="store_true",
        help="Only write records with status=resolved",
    )
    p_scan.set_defaults(func=_run_scan)

    args = parser.parse_args(argv)
    return int(args.func(args))


def _run_scan(args: argparse.Namespace) -> int:
    domain = str(args.domain).strip().strip(".").lower()
    if not domain:
        print("error: --domain must be non-empty", file=sys.stderr)
        return 2
    out_path = None if args.out == "-" else Path(args.out)
    try:
        summary = scan_domains_summary(
            domain=domain,
            wordlist=Path(args.wordlist),
            out_path=out_path,
            timeout=args.timeout,
            concurrency=args.concurrency,
            only_resolved=bool(args.only_resolved),
        )
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    dest = "stdout" if out_path is None else str(out_path)
    print(
        "scanned"
        f" attempted={summary.attempted}"
        f" resolved={summary.resolved}"
        f" not_found={summary.not_found}"
        f" error={summary.error}"
        f" wrote={summary.written}"
        f" elapsed_ms={summary.elapsed_ms}"
        f" out={dest}",
        file=sys.stderr,
    )
    return 1 if summary.error else 0


if __name__ == "__main__":
    raise SystemExit(main())
