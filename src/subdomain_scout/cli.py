from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

from .diff import compute_diff, load_jsonl
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
        "--summary-json",
        action="store_true",
        help="Print scan summary as JSON to stderr",
    )
    p_scan.add_argument(
        "--status",
        action="append",
        choices=["resolved", "not_found", "error", "wildcard"],
        help="Only write records with these statuses (repeatable)",
    )
    p_scan.add_argument(
        "--detect-wildcard",
        action="store_true",
        help="Best-effort wildcard DNS detection (marks matching records as status=wildcard)",
    )
    p_scan.add_argument(
        "--wildcard-probes",
        type=int,
        default=2,
        help="Number of random probes used for wildcard detection (>= 2)",
    )
    p_scan.add_argument(
        "--only-resolved",
        action="store_true",
        help="Only write records with status=resolved",
    )
    p_scan.add_argument("--retries", type=int, default=0, help="Retries for transient DNS errors")
    p_scan.add_argument(
        "--retry-backoff-ms",
        type=int,
        default=50,
        help="Base backoff for retries (exponential)",
    )
    p_scan.set_defaults(func=_run_scan)

    p_diff = sub.add_parser("diff", help="Diff two JSONL/NDJSON scan outputs")
    p_diff.add_argument("--old", required=True, help="Old JSONL path (use '-' for stdin)")
    p_diff.add_argument("--new", required=True, help="New JSONL path (use '-' for stdin)")
    p_diff.add_argument(
        "--resolved-only",
        action="store_true",
        help="Only consider records with status=resolved",
    )
    p_diff.add_argument(
        "--only",
        action="append",
        choices=["added", "removed", "changed"],
        help="Only emit these change kinds (repeatable)",
    )
    p_diff.add_argument("--summary-only", action="store_true", help="Only print summary to stderr")
    p_diff.add_argument(
        "--summary-json",
        action="store_true",
        help="Print diff summary as JSON to stderr",
    )
    p_diff.add_argument(
        "--fail-on-changes", action="store_true", help="Exit non-zero if any changes"
    )
    p_diff.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Skip invalid JSONL lines instead of failing",
    )
    p_diff.set_defaults(func=_run_diff)

    args = parser.parse_args(argv)
    return int(args.func(args))


def _run_scan(args: argparse.Namespace) -> int:
    domain = str(args.domain).strip().strip(".").lower()
    if not domain:
        print("error: --domain must be non-empty", file=sys.stderr)
        return 2
    if args.only_resolved and args.status:
        print("error: --only-resolved and --status cannot both be set", file=sys.stderr)
        return 2
    out_path = None if args.out == "-" else Path(args.out)
    try:
        summary = scan_domains_summary(
            domain=domain,
            wordlist=Path(args.wordlist),
            out_path=out_path,
            timeout=args.timeout,
            concurrency=args.concurrency,
            statuses=set(args.status) if args.status else None,
            detect_wildcard=bool(args.detect_wildcard),
            wildcard_probes=args.wildcard_probes,
            only_resolved=bool(args.only_resolved),
            retries=args.retries,
            retry_backoff_ms=args.retry_backoff_ms,
        )
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    dest = "stdout" if out_path is None else str(out_path)
    if args.summary_json:
        sys.stderr.write(
            json.dumps(
                {
                    "kind": "scan_summary",
                    "attempted": summary.attempted,
                    "resolved": summary.resolved,
                    "wildcard": summary.wildcard,
                    "not_found": summary.not_found,
                    "error": summary.error,
                    "wrote": summary.written,
                    "elapsed_ms": summary.elapsed_ms,
                    "out": dest,
                }
            )
            + "\n"
        )
    else:
        print(
            "scanned"
            f" attempted={summary.attempted}"
            f" resolved={summary.resolved}"
            f" wildcard={summary.wildcard}"
            f" not_found={summary.not_found}"
            f" error={summary.error}"
            f" wrote={summary.written}"
            f" elapsed_ms={summary.elapsed_ms}"
            f" out={dest}",
            file=sys.stderr,
        )
    return 1 if summary.error else 0


def _run_diff(args: argparse.Namespace) -> int:
    use_old_stdin = args.old == "-"
    use_new_stdin = args.new == "-"
    if use_old_stdin and use_new_stdin:
        print("error: only one of --old/--new may be '-'", file=sys.stderr)
        return 2

    only_kinds = set(args.only or ["added", "removed", "changed"])

    try:
        with contextlib.ExitStack() as stack:
            old_stream = (
                sys.stdin
                if use_old_stdin
                else stack.enter_context(Path(args.old).open("r", encoding="utf-8"))
            )
            new_stream = (
                sys.stdin
                if use_new_stdin
                else stack.enter_context(Path(args.new).open("r", encoding="utf-8"))
            )

            old = load_jsonl(
                old_stream,
                src=str(args.old),
                resolved_only=bool(args.resolved_only),
                skip_invalid=bool(args.skip_invalid),
            )
            new = load_jsonl(
                new_stream,
                src=str(args.new),
                resolved_only=bool(args.resolved_only),
                skip_invalid=bool(args.skip_invalid),
            )
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    summary, events = compute_diff(old, new)
    for event in events:
        if event["kind"] in only_kinds and not args.summary_only:
            sys.stdout.write(json.dumps(event) + "\n")

    changed_total = summary.added + summary.removed + summary.changed
    if args.summary_json:
        sys.stderr.write(
            json.dumps(
                {
                    "kind": "diff_summary",
                    "old": summary.old_total,
                    "new": summary.new_total,
                    "added": summary.added,
                    "removed": summary.removed,
                    "changed": summary.changed,
                    "unchanged": summary.unchanged,
                }
            )
            + "\n"
        )
    else:
        print(
            "diff"
            f" old={summary.old_total}"
            f" new={summary.new_total}"
            f" added={summary.added}"
            f" removed={summary.removed}"
            f" changed={summary.changed}"
            f" unchanged={summary.unchanged}",
            file=sys.stderr,
        )
    return 1 if args.fail_on_changes and changed_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
