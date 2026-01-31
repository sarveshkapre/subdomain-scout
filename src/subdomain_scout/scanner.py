from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Result:
    subdomain: str
    ips: list[str]
    status: str
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "subdomain": self.subdomain,
            "ips": self.ips,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
        }


def _resolve(name: str, timeout: float) -> Result:
    start = time.time()
    try:
        socket.setdefaulttimeout(timeout)
        infos = socket.getaddrinfo(name, None)
        ips = [info[4][0] for info in infos]
        ips = list(dict.fromkeys(ips))
        return Result(subdomain=name, ips=ips, status="resolved", elapsed_ms=_ms(start))
    except socket.gaierror:
        return Result(subdomain=name, ips=[], status="not_found", elapsed_ms=_ms(start))
    except OSError:
        return Result(subdomain=name, ips=[], status="error", elapsed_ms=_ms(start))


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def scan_domains(domain: str, wordlist: Path, out_path: Path, timeout: float) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wordlist.open("r", encoding="utf-8") as fh, out_path.open("w", encoding="utf-8") as out:
        for line in fh:
            label = line.strip()
            if not label:
                continue
            sub = f"{label}.{domain}"
            res = _resolve(sub, timeout)
            out.write(json.dumps(res.to_dict()) + "\n")
    print(f"wrote {out_path}")
    return 0
