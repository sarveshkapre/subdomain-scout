from __future__ import annotations

import contextlib
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO


@dataclass(frozen=True)
class Result:
    subdomain: str
    ips: list[str]
    status: str
    elapsed_ms: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subdomain": self.subdomain,
            "ips": self.ips,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


def _resolve(name: str) -> Result:
    start = time.time()
    try:
        infos = socket.getaddrinfo(name, None)
        ips = [info[4][0] for info in infos]
        ips = list(dict.fromkeys(ips))
        return Result(subdomain=name, ips=ips, status="resolved", elapsed_ms=_ms(start))
    except socket.gaierror as e:
        not_found_errnos = {
            errno
            for errno in (getattr(socket, "EAI_NONAME", None), getattr(socket, "EAI_NODATA", None))
            if errno is not None
        }
        if e.errno in not_found_errnos:
            return Result(subdomain=name, ips=[], status="not_found", elapsed_ms=_ms(start))
        return Result(subdomain=name, ips=[], status="error", elapsed_ms=_ms(start), error=str(e))
    except OSError as e:
        return Result(subdomain=name, ips=[], status="error", elapsed_ms=_ms(start), error=str(e))


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


@dataclass(frozen=True)
class ScanSummary:
    attempted: int
    written: int
    resolved: int
    not_found: int
    error: int
    elapsed_ms: int


def _iter_labels(wordlist: Path) -> Iterable[str]:
    with wordlist.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            label = line.split(maxsplit=1)[0].strip(".")
            if not label or label.startswith("#"):
                continue
            yield label


def _iter_fqdns(domain: str, wordlist: Path) -> Iterable[str]:
    for label in _iter_labels(wordlist):
        yield f"{label}.{domain}"


@contextlib.contextmanager
def _output_stream(out_path: Path | None) -> Iterator[tuple[TextIO, Path | None]]:
    if out_path is None:
        yield sys.stdout, None
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as out:
        yield out, tmp_path
    tmp_path.replace(out_path)


def scan_domains(domain: str, wordlist: Path, out_path: Path, timeout: float) -> int:
    scan_domains_summary(domain=domain, wordlist=wordlist, out_path=out_path, timeout=timeout)
    return 0


def scan_domains_summary(
    *,
    domain: str,
    wordlist: Path,
    out_path: Path | None,
    timeout: float,
    concurrency: int = 20,
    only_resolved: bool = False,
) -> ScanSummary:
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if timeout <= 0:
        raise ValueError("timeout must be > 0")

    start = time.time()
    attempted = 0
    written = 0
    resolved = 0
    not_found = 0
    error = 0

    prev_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        executor: ThreadPoolExecutor | None = None
        if concurrency > 1:
            executor = ThreadPoolExecutor(max_workers=concurrency)

        def run_one(name: str) -> Result:
            return _resolve(name)

        with contextlib.ExitStack() as stack:
            if executor is not None:
                stack.enter_context(executor)

            out, _tmp_path = stack.enter_context(_output_stream(out_path))
            names = _iter_fqdns(domain, wordlist)

            if executor is None:
                results: Iterable[Result] = (run_one(name) for name in names)
            else:
                results = executor.map(run_one, names)

            for res in results:
                attempted += 1
                if res.status == "resolved":
                    resolved += 1
                elif res.status == "not_found":
                    not_found += 1
                else:
                    error += 1

                if only_resolved and res.status != "resolved":
                    continue
                out.write(json.dumps(res.to_dict()) + "\n")
                written += 1
    finally:
        socket.setdefaulttimeout(prev_timeout)

    return ScanSummary(
        attempted=attempted,
        written=written,
        resolved=resolved,
        not_found=not_found,
        error=error,
        elapsed_ms=_ms(start),
    )
