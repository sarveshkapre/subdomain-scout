from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

from .ct import fetch_ct_subdomains, subdomains_to_labels
from .dns_client import load_nameservers_file, parse_nameserver
from .diff import compute_diff, load_jsonl
from .scanner import scan_domains_summary, scan_domains_summary_lines
from .takeover import build_takeover_checker
from .validation import normalize_domain
from .version import get_version

_SCHEMA_VERSION = 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subdomain-scout")
    parser.add_argument("--version", action="version", version=get_version())

    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="Scan subdomains from wordlist")
    p_scan.add_argument("--domain", required=True)
    p_scan.add_argument("--wordlist", required=True, help="Wordlist path (use '-' for stdin)")
    p_scan.add_argument(
        "--out",
        default="subdomains.jsonl",
        help="Output path (use '-' for stdout)",
    )
    p_scan.add_argument("--timeout", type=float, default=3.0)
    p_scan.add_argument(
        "--resolver",
        action="append",
        default=None,
        help="Custom DNS resolver IP[:port] (repeatable; supports [IPv6]:port). When set, bypasses the system resolver.",
    )
    p_scan.add_argument(
        "--resolver-file",
        default=None,
        help="Path to resolver list file (one IP[:port] per line; '#' comments allowed). When set, bypasses the system resolver.",
    )
    p_scan.add_argument(
        "--include-cname",
        action="store_true",
        help="Include observed CNAME chain in output records and classify CNAME-only results as status=cname (requires --resolver/--resolver-file).",
    )
    p_scan.add_argument(
        "--resume",
        action="store_true",
        help="Resume/append mode: skip labels already present in the existing --out file and append new results.",
    )
    p_scan.add_argument("--concurrency", type=int, default=20)
    p_scan.add_argument(
        "--summary-json",
        action="store_true",
        help="Print scan summary as JSON to stderr",
    )
    p_scan.add_argument(
        "--progress",
        action="store_true",
        help="Print periodic progress updates to stderr (incompatible with --summary-json)",
    )
    p_scan.add_argument(
        "--progress-every",
        type=float,
        default=2.0,
        help="Progress update interval in seconds (0 = every record; used with --progress)",
    )
    p_scan.add_argument(
        "--ct",
        action="store_true",
        help="Include labels discovered from certificate transparency logs (crt.sh)",
    )
    p_scan.add_argument(
        "--ct-timeout",
        type=float,
        default=10.0,
        help="Timeout for CT lookups in seconds (used with --ct)",
    )
    p_scan.add_argument(
        "--ct-limit",
        type=int,
        default=0,
        help="Max CT subdomains to ingest (0 = unlimited)",
    )
    p_scan.add_argument(
        "--status",
        action="append",
        choices=["resolved", "not_found", "error", "wildcard", "cname"],
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
        "--wildcard-threshold",
        type=int,
        default=1,
        help="Only start classifying records as wildcard after this many wildcard IP-set matches (>= 1).",
    )
    p_scan.add_argument(
        "--wildcard-verify-http",
        action="store_true",
        help="Reduce wildcard false positives on CDNs by comparing HTTP responses against a random wildcard probe (requires --detect-wildcard).",
    )
    p_scan.add_argument(
        "--wildcard-http-timeout",
        type=float,
        default=3.0,
        help="Timeout for wildcard HTTP verification probes in seconds (used with --wildcard-verify-http).",
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
    p_scan.add_argument(
        "--takeover-check",
        action="store_true",
        help="Probe resolved hosts for known subdomain takeover fingerprints",
    )
    p_scan.add_argument(
        "--takeover-timeout",
        type=float,
        default=3.0,
        help="Timeout for takeover HTTP probes in seconds (used with --takeover-check)",
    )
    p_scan.add_argument(
        "--takeover-fingerprints",
        default=None,
        help="Path to custom takeover fingerprint catalog JSON (used with --takeover-check)",
    )
    p_scan.set_defaults(func=_run_scan)

    p_ct = sub.add_parser("ct", help="Fetch passive subdomains from certificate transparency logs")
    p_ct.add_argument("--domain", required=True)
    p_ct.add_argument(
        "--out",
        default="-",
        help="Output path (use '-' for stdout)",
    )
    p_ct.add_argument("--timeout", type=float, default=10.0)
    p_ct.add_argument("--limit", type=int, default=0, help="Max results to emit (0 = unlimited)")
    p_ct.add_argument(
        "--summary-json",
        action="store_true",
        help="Print CT fetch summary as JSON to stderr",
    )
    p_ct.set_defaults(func=_run_ct)

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
    try:
        domain = normalize_domain(str(args.domain))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.only_resolved and args.status:
        print("error: --only-resolved and --status cannot both be set", file=sys.stderr)
        return 2
    if args.progress and args.summary_json:
        print("error: --progress and --summary-json cannot both be set", file=sys.stderr)
        return 2
    if args.wildcard_verify_http and not args.detect_wildcard:
        print("error: --wildcard-verify-http requires --detect-wildcard", file=sys.stderr)
        return 2
    if int(args.wildcard_threshold) < 1:
        print("error: --wildcard-threshold must be >= 1", file=sys.stderr)
        return 2
    if args.wildcard_verify_http and float(args.wildcard_http_timeout) <= 0:
        print("error: --wildcard-http-timeout must be > 0", file=sys.stderr)
        return 2

    ct_labels: list[str] = []
    takeover_checker = None
    if args.ct:
        limit = None if args.ct_limit == 0 else int(args.ct_limit)
        try:
            ct_subdomains, _ct_summary = fetch_ct_subdomains(
                domain,
                timeout=float(args.ct_timeout),
                limit=limit,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        except OSError as e:
            print(f"error: CT lookup failed: {e}", file=sys.stderr)
            return 1
        ct_labels = subdomains_to_labels(ct_subdomains, domain=domain)

    if args.takeover_check:
        fingerprints_path = (
            None if args.takeover_fingerprints is None else Path(str(args.takeover_fingerprints))
        )
        try:
            takeover_checker = build_takeover_checker(
                timeout=float(args.takeover_timeout),
                fingerprints_path=fingerprints_path,
            )
        except FileNotFoundError as e:
            print(f"error: file not found: {e.filename}", file=sys.stderr)
            return 2
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    nameservers = None
    if args.resolver_file or args.resolver:
        try:
            resolvers: list[tuple[str, int]] = []
            if args.resolver_file:
                resolvers.extend(load_nameservers_file(Path(str(args.resolver_file))))
            if args.resolver:
                resolvers.extend(parse_nameserver(s) for s in args.resolver)
            # Dedup while preserving order.
            seen: set[tuple[str, int]] = set()
            nameservers = []
            for item in resolvers:
                if item in seen:
                    continue
                seen.add(item)
                nameservers.append(item)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    if args.include_cname and nameservers is None:
        print(
            "error: --include-cname requires --resolver/--resolver-file (custom resolver mode)",
            file=sys.stderr,
        )
        return 2

    out_path = None if args.out == "-" else Path(args.out)
    try:
        progress_stream = sys.stderr if args.progress else None
        progress_every_s = float(args.progress_every)
        if args.wordlist == "-":
            summary = scan_domains_summary_lines(
                domain=domain,
                wordlist_lines=sys.stdin,
                out_path=out_path,
                timeout=args.timeout,
                concurrency=args.concurrency,
                statuses=set(args.status) if args.status else None,
                detect_wildcard=bool(args.detect_wildcard),
                wildcard_probes=args.wildcard_probes,
                wildcard_threshold=args.wildcard_threshold,
                wildcard_verify_http=bool(args.wildcard_verify_http),
                wildcard_http_timeout=float(args.wildcard_http_timeout),
                include_cname=bool(args.include_cname),
                progress_stream=progress_stream,
                progress_every_s=progress_every_s,
                only_resolved=bool(args.only_resolved),
                retries=args.retries,
                retry_backoff_ms=args.retry_backoff_ms,
                extra_labels=ct_labels,
                ct_labels_count=len(ct_labels),
                takeover_checker=takeover_checker,
                nameservers=nameservers,
                resume=bool(args.resume),
            )
        else:
            summary = scan_domains_summary(
                domain=domain,
                wordlist=Path(args.wordlist),
                out_path=out_path,
                timeout=args.timeout,
                concurrency=args.concurrency,
                statuses=set(args.status) if args.status else None,
                detect_wildcard=bool(args.detect_wildcard),
                wildcard_probes=args.wildcard_probes,
                wildcard_threshold=args.wildcard_threshold,
                wildcard_verify_http=bool(args.wildcard_verify_http),
                wildcard_http_timeout=float(args.wildcard_http_timeout),
                include_cname=bool(args.include_cname),
                progress_stream=progress_stream,
                progress_every_s=progress_every_s,
                only_resolved=bool(args.only_resolved),
                retries=args.retries,
                retry_backoff_ms=args.retry_backoff_ms,
                extra_labels=ct_labels,
                ct_labels_count=len(ct_labels),
                takeover_checker=takeover_checker,
                nameservers=nameservers,
                resume=bool(args.resume),
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
                    "schema_version": _SCHEMA_VERSION,
                    "attempted": summary.attempted,
                    "resolved": summary.resolved,
                    "wildcard": summary.wildcard,
                    "cname": summary.cname,
                    "not_found": summary.not_found,
                    "error": summary.error,
                    "wrote": summary.written,
                    "labels_total": summary.labels_total,
                    "labels_unique": summary.labels_unique,
                    "labels_deduped": summary.labels_deduped,
                    "labels_skipped_existing": summary.labels_skipped_existing,
                    "ct_labels": summary.ct_labels,
                    "takeover_checked": summary.takeover_checked,
                    "takeover_suspected": summary.takeover_suspected,
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
            f" cname={summary.cname}"
            f" not_found={summary.not_found}"
            f" error={summary.error}"
            f" wrote={summary.written}"
            f" labels_total={summary.labels_total}"
            f" labels_unique={summary.labels_unique}"
            f" labels_deduped={summary.labels_deduped}"
            f" labels_skipped_existing={summary.labels_skipped_existing}"
            f" ct_labels={summary.ct_labels}"
            f" takeover_checked={summary.takeover_checked}"
            f" takeover_suspected={summary.takeover_suspected}"
            f" elapsed_ms={summary.elapsed_ms}"
            f" out={dest}",
            file=sys.stderr,
        )
    return 1 if summary.error else 0


def _run_ct(args: argparse.Namespace) -> int:
    try:
        domain = normalize_domain(str(args.domain))
        limit = None if args.limit == 0 else int(args.limit)
        subdomains, summary = fetch_ct_subdomains(domain, timeout=float(args.timeout), limit=limit)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: CT lookup failed: {e}", file=sys.stderr)
        return 1

    out = sys.stdout
    if args.out != "-":
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out = out_path.open("w", encoding="utf-8")
    try:
        for subdomain in subdomains:
            out.write(
                json.dumps(
                    {
                        "subdomain": subdomain,
                        "source": "crt.sh",
                        "status": "passive",
                    }
                )
                + "\n"
            )
    finally:
        if out is not sys.stdout:
            out.close()

    dest = "stdout" if args.out == "-" else str(args.out)
    if args.summary_json:
        sys.stderr.write(
            json.dumps(
                {
                    "kind": "ct_summary",
                    "schema_version": _SCHEMA_VERSION,
                    "records_fetched": summary.records_fetched,
                    "names_seen": summary.names_seen,
                    "emitted": summary.emitted,
                    "elapsed_ms": summary.elapsed_ms,
                    "out": dest,
                }
            )
            + "\n"
        )
    else:
        print(
            "ct"
            f" records_fetched={summary.records_fetched}"
            f" names_seen={summary.names_seen}"
            f" emitted={summary.emitted}"
            f" elapsed_ms={summary.elapsed_ms}"
            f" out={dest}",
            file=sys.stderr,
        )
    return 0


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
                    "schema_version": _SCHEMA_VERSION,
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
