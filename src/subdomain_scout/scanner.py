from __future__ import annotations

import contextlib
import itertools
import json
import secrets
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, TextIO

from .dns_client import DnsQueryError, resolve_ips
from .validation import normalize_label


@dataclass(frozen=True)
class Result:
    subdomain: str
    ips: list[str]
    status: str
    elapsed_ms: int
    attempts: int = 1
    retries: int = 0
    error: str | None = None
    error_type: str | None = None
    error_code: int | None = None
    takeover: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subdomain": self.subdomain,
            "ips": self.ips,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "attempts": self.attempts,
            "retries": self.retries,
        }
        if self.error is not None:
            payload["error"] = self.error
        if self.error_type is not None:
            payload["error_type"] = self.error_type
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        if self.takeover is not None:
            payload["takeover"] = self.takeover
        return payload


def _resolve(name: str, *, timeout: float, nameservers: list[tuple[str, int]] | None) -> Result:
    start = time.time()
    try:
        if nameservers is None:
            infos = socket.getaddrinfo(name, None)
            ips = [info[4][0] for info in infos]
            ips = list(dict.fromkeys(ips))
        else:
            ips = resolve_ips(name, nameservers=nameservers, timeout=timeout)
            if not ips:
                return Result(subdomain=name, ips=[], status="not_found", elapsed_ms=_ms(start))
        return Result(subdomain=name, ips=ips, status="resolved", elapsed_ms=_ms(start))
    except socket.gaierror as e:
        not_found_errnos = {
            errno
            for errno in (getattr(socket, "EAI_NONAME", None), getattr(socket, "EAI_NODATA", None))
            if errno is not None
        }
        if e.errno in not_found_errnos:
            return Result(subdomain=name, ips=[], status="not_found", elapsed_ms=_ms(start))
        return Result(
            subdomain=name,
            ips=[],
            status="error",
            elapsed_ms=_ms(start),
            error=str(e),
            error_type="gaierror",
            error_code=e.errno,
        )
    except TimeoutError as e:
        return Result(
            subdomain=name,
            ips=[],
            status="error",
            elapsed_ms=_ms(start),
            error=str(e),
            error_type="timeout",
            error_code=None,
        )
    except DnsQueryError as e:
        if e.rcode == 3:
            return Result(subdomain=name, ips=[], status="not_found", elapsed_ms=_ms(start))
        return Result(
            subdomain=name,
            ips=[],
            status="error",
            elapsed_ms=_ms(start),
            error=str(e),
            error_type="dns",
            error_code=e.rcode,
        )
    except OSError as e:
        return Result(
            subdomain=name,
            ips=[],
            status="error",
            elapsed_ms=_ms(start),
            error=str(e),
            error_type="oserror",
            error_code=e.errno,
        )


def _is_retryable(res: Result) -> bool:
    eai_again = getattr(socket, "EAI_AGAIN", None)
    if res.status != "error":
        return False
    if res.error_type == "gaierror" and res.error_code == eai_again:
        return True
    if res.error_type == "timeout":
        return True
    return False


def _resolve_with_retries(
    name: str,
    *,
    timeout: float,
    nameservers: list[tuple[str, int]] | None,
    retries: int,
    retry_backoff_ms: int,
) -> Result:
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if retry_backoff_ms < 0:
        raise ValueError("retry_backoff_ms must be >= 0")

    attempt = 0
    while True:
        res = _resolve(name, timeout=timeout, nameservers=nameservers)
        attempts = attempt + 1
        if res.status != "error":
            return Result(
                subdomain=res.subdomain,
                ips=res.ips,
                status=res.status,
                elapsed_ms=res.elapsed_ms,
                attempts=attempts,
                retries=attempt,
                error=res.error,
                error_type=res.error_type,
                error_code=res.error_code,
            )
        if not _is_retryable(res):
            return Result(
                subdomain=res.subdomain,
                ips=res.ips,
                status=res.status,
                elapsed_ms=res.elapsed_ms,
                attempts=attempts,
                retries=attempt,
                error=res.error,
                error_type=res.error_type,
                error_code=res.error_code,
            )
        if attempt >= retries:
            return Result(
                subdomain=res.subdomain,
                ips=res.ips,
                status=res.status,
                elapsed_ms=res.elapsed_ms,
                attempts=attempts,
                retries=attempt,
                error=res.error,
                error_type=res.error_type,
                error_code=res.error_code,
            )
        if retry_backoff_ms:
            time.sleep((retry_backoff_ms * (2**attempt)) / 1000.0)
        attempt += 1


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


@dataclass(frozen=True)
class ScanSummary:
    attempted: int
    written: int
    resolved: int
    wildcard: int
    not_found: int
    error: int
    labels_total: int
    labels_unique: int
    labels_deduped: int
    labels_skipped_existing: int
    ct_labels: int
    takeover_checked: int
    takeover_suspected: int
    elapsed_ms: int


def _iter_labels_lines(lines: Iterable[str]) -> Iterable[str]:
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        label = line.split(maxsplit=1)[0].strip(".")
        if not label or label.startswith("#"):
            continue
        yield normalize_label(label)


def _iter_labels(wordlist: Path) -> Iterable[str]:
    with wordlist.open("r", encoding="utf-8") as fh:
        yield from _iter_labels_lines(fh)


def _iter_fqdns(domain: str, labels: Iterable[str]) -> Iterable[str]:
    for label in labels:
        yield f"{label}.{domain}"


@contextlib.contextmanager
def _output_stream(out_path: Path | None, *, append: bool) -> Iterator[tuple[TextIO, Path | None]]:
    if out_path is None:
        yield sys.stdout, None
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with out_path.open("a", encoding="utf-8") as out:
            yield out, None
        return
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as out:
        yield out, tmp_path
    tmp_path.replace(out_path)


def scan_domains(domain: str, wordlist: Path, out_path: Path, timeout: float) -> int:
    scan_domains_summary(domain=domain, wordlist=wordlist, out_path=out_path, timeout=timeout)
    return 0


def _scan_core(
    *,
    domain: str,
    labels: Iterable[str],
    out_path: Path | None,
    timeout: float,
    concurrency: int,
    statuses: set[str] | None,
    detect_wildcard: bool,
    wildcard_probes: int,
    retries: int,
    retry_backoff_ms: int,
    ct_labels: int,
    takeover_checker: Callable[[str], dict[str, Any] | None] | None,
    nameservers: list[tuple[str, int]] | None,
    resume_seen_labels: set[str] | None,
    append_out: bool,
) -> ScanSummary:
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if timeout <= 0:
        raise ValueError("timeout must be > 0")
    if detect_wildcard and wildcard_probes < 2:
        raise ValueError("wildcard_probes must be >= 2 when detect_wildcard is enabled")

    start = time.time()
    attempted = 0
    written = 0
    resolved = 0
    wildcard = 0
    not_found = 0
    error = 0
    labels_total = 0
    labels_unique = 0
    labels_deduped = 0
    labels_skipped_existing = 0
    takeover_checked = 0
    takeover_suspected = 0

    allowed_statuses = {"resolved", "wildcard", "not_found", "error"}
    if statuses is not None:
        unknown = statuses - allowed_statuses
        if unknown:
            raise ValueError(f"unknown statuses: {', '.join(sorted(unknown))}")

    prev_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        wildcard_cache: dict[str, set[frozenset[str]]] = {}

        def wildcard_ipsets_for_zone(zone: str) -> set[frozenset[str]]:
            cached = wildcard_cache.get(zone)
            if cached is not None:
                return cached
            hits = _detect_wildcard_ipsets(
                zone, probes=wildcard_probes, timeout=timeout, nameservers=nameservers
            )
            ipsets = {ipset for ipset, count in hits.items() if count >= 2}
            wildcard_cache[zone] = ipsets
            return ipsets

        executor: ThreadPoolExecutor | None = None
        if concurrency > 1:
            executor = ThreadPoolExecutor(max_workers=concurrency)

        def run_one(name: str) -> Result:
            return _resolve_with_retries(
                name,
                timeout=timeout,
                nameservers=nameservers,
                retries=retries,
                retry_backoff_ms=retry_backoff_ms,
            )

        with contextlib.ExitStack() as stack:
            if executor is not None:
                stack.enter_context(executor)

            out, _tmp_path = stack.enter_context(_output_stream(out_path, append=append_out))

            seen_labels: set[str] = set()

            def iter_unique_labels() -> Iterator[str]:
                nonlocal labels_total, labels_unique, labels_deduped, labels_skipped_existing
                for label in labels:
                    labels_total += 1
                    if label in seen_labels:
                        labels_deduped += 1
                        continue
                    seen_labels.add(label)
                    labels_unique += 1
                    if resume_seen_labels is not None and label in resume_seen_labels:
                        labels_skipped_existing += 1
                        continue
                    yield label

            names = _iter_fqdns(domain, iter_unique_labels())

            if executor is None:
                results: Iterable[Result] = (run_one(name) for name in names)
            else:
                results = executor.map(run_one, names)

            for res in results:
                attempted += 1
                if detect_wildcard and res.status == "resolved" and res.ips:
                    # Handle multi-level wildcards by probing the immediate suffix of the hostname.
                    # Example: for "foo.dev.example.com", probe "*.dev.example.com".
                    parts = res.subdomain.split(".", 1)
                    if len(parts) == 2:
                        zone = parts[1]
                        ipsets = wildcard_ipsets_for_zone(zone)
                        if ipsets and frozenset(res.ips) in ipsets:
                            res = Result(
                                subdomain=res.subdomain,
                                ips=res.ips,
                                status="wildcard",
                                elapsed_ms=res.elapsed_ms,
                                attempts=res.attempts,
                                retries=res.retries,
                                error=res.error,
                                error_type=res.error_type,
                                error_code=res.error_code,
                                takeover=res.takeover,
                            )

                if takeover_checker is not None and res.status in {"resolved", "wildcard"}:
                    takeover_checked += 1
                    try:
                        takeover = takeover_checker(res.subdomain)
                    except OSError:
                        takeover = None
                    if takeover is not None:
                        takeover_suspected += 1
                        res = Result(
                            subdomain=res.subdomain,
                            ips=res.ips,
                            status=res.status,
                            elapsed_ms=res.elapsed_ms,
                            attempts=res.attempts,
                            retries=res.retries,
                            error=res.error,
                            error_type=res.error_type,
                            error_code=res.error_code,
                            takeover=takeover,
                        )

                if res.status == "resolved":
                    resolved += 1
                elif res.status == "wildcard":
                    wildcard += 1
                elif res.status == "not_found":
                    not_found += 1
                else:
                    error += 1

                if statuses is not None and res.status not in statuses:
                    continue
                out.write(json.dumps(res.to_dict()) + "\n")
                written += 1
    finally:
        socket.setdefaulttimeout(prev_timeout)

    return ScanSummary(
        attempted=attempted,
        written=written,
        resolved=resolved,
        wildcard=wildcard,
        not_found=not_found,
        error=error,
        labels_total=labels_total,
        labels_unique=labels_unique,
        labels_deduped=labels_deduped,
        labels_skipped_existing=labels_skipped_existing,
        ct_labels=ct_labels,
        takeover_checked=takeover_checked,
        takeover_suspected=takeover_suspected,
        elapsed_ms=_ms(start),
    )


def scan_domains_summary(
    *,
    domain: str,
    wordlist: Path,
    out_path: Path | None,
    timeout: float,
    concurrency: int = 20,
    only_resolved: bool = False,
    statuses: set[str] | None = None,
    detect_wildcard: bool = False,
    wildcard_probes: int = 2,
    retries: int = 0,
    retry_backoff_ms: int = 50,
    extra_labels: Iterable[str] | None = None,
    ct_labels_count: int = 0,
    takeover_checker: Callable[[str], dict[str, Any] | None] | None = None,
    nameservers: list[tuple[str, int]] | None = None,
    resume: bool = False,
) -> ScanSummary:
    if only_resolved and statuses is not None:
        raise ValueError("only_resolved and statuses cannot both be set")
    if only_resolved:
        statuses = {"resolved"}
    labels = _iter_labels(wordlist)
    if extra_labels:
        labels = itertools.chain(labels, extra_labels)
    resume_seen_labels = _load_resume_labels(out_path, domain=domain) if resume else None
    return _scan_core(
        domain=domain,
        labels=labels,
        out_path=out_path,
        timeout=timeout,
        concurrency=concurrency,
        statuses=statuses,
        detect_wildcard=detect_wildcard,
        wildcard_probes=wildcard_probes,
        retries=retries,
        retry_backoff_ms=retry_backoff_ms,
        ct_labels=ct_labels_count,
        takeover_checker=takeover_checker,
        nameservers=nameservers,
        resume_seen_labels=resume_seen_labels,
        append_out=bool(resume),
    )


def scan_domains_summary_lines(
    *,
    domain: str,
    wordlist_lines: Iterable[str],
    out_path: Path | None,
    timeout: float,
    concurrency: int = 20,
    only_resolved: bool = False,
    statuses: set[str] | None = None,
    detect_wildcard: bool = False,
    wildcard_probes: int = 2,
    retries: int = 0,
    retry_backoff_ms: int = 50,
    extra_labels: Iterable[str] | None = None,
    ct_labels_count: int = 0,
    takeover_checker: Callable[[str], dict[str, Any] | None] | None = None,
    nameservers: list[tuple[str, int]] | None = None,
    resume: bool = False,
) -> ScanSummary:
    if only_resolved and statuses is not None:
        raise ValueError("only_resolved and statuses cannot both be set")
    if only_resolved:
        statuses = {"resolved"}
    labels = _iter_labels_lines(wordlist_lines)
    if extra_labels:
        labels = itertools.chain(labels, extra_labels)
    resume_seen_labels = _load_resume_labels(out_path, domain=domain) if resume else None
    return _scan_core(
        domain=domain,
        labels=labels,
        out_path=out_path,
        timeout=timeout,
        concurrency=concurrency,
        statuses=statuses,
        detect_wildcard=detect_wildcard,
        wildcard_probes=wildcard_probes,
        retries=retries,
        retry_backoff_ms=retry_backoff_ms,
        ct_labels=ct_labels_count,
        takeover_checker=takeover_checker,
        nameservers=nameservers,
        resume_seen_labels=resume_seen_labels,
        append_out=bool(resume),
    )


def detect_wildcard_ips(
    domain: str,
    *,
    probes: int = 2,
    timeout: float = 3.0,
    nameservers: list[tuple[str, int]] | None = None,
) -> set[str] | None:
    ipsets = _detect_wildcard_ipsets(domain, probes=probes, timeout=timeout, nameservers=nameservers)
    if not ipsets:
        return None
    # Back-compat: return the "strongest" (most frequently observed) ipset.
    best = max(ipsets.items(), key=lambda kv: kv[1])[0]
    return set(best)


def _detect_wildcard_ipsets(
    zone: str,
    *,
    probes: int,
    timeout: float,
    nameservers: list[tuple[str, int]] | None,
) -> dict[frozenset[str], int]:
    hits: dict[frozenset[str], int] = {}
    for _ in range(probes):
        label = f"_sdscout-{secrets.token_hex(8)}"
        res = _resolve(f"{label}.{zone}", timeout=timeout, nameservers=nameservers)
        if res.status != "resolved" or not res.ips:
            continue
        ipset = frozenset(res.ips)
        hits[ipset] = hits.get(ipset, 0) + 1
    return hits


def _load_resume_labels(out_path: Path | None, *, domain: str) -> set[str]:
    if out_path is None:
        raise ValueError("resume requires file output (--out path, not '-')")
    if not out_path.exists():
        return set()

    suffix = f".{domain}"
    seen: set[str] = set()
    with out_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            subdomain_raw = obj.get("subdomain")
            if not isinstance(subdomain_raw, str):
                continue
            subdomain = subdomain_raw.strip().strip(".").lower()
            if not subdomain.endswith(suffix) or subdomain == domain:
                continue
            label = subdomain[: -len(suffix)]
            if not label:
                continue
            try:
                normalized = normalize_label(label)
            except ValueError:
                continue
            seen.add(normalized)
    return seen
