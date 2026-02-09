from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from .validation import normalize_label


@dataclass(frozen=True)
class CtFetchSummary:
    records_fetched: int
    names_seen: int
    emitted: int
    elapsed_ms: int


def fetch_ct_subdomains(
    domain: str, *, timeout: float = 10.0, limit: int | None = None
) -> tuple[list[str], CtFetchSummary]:
    if timeout <= 0:
        raise ValueError("ct timeout must be > 0")
    if limit is not None and limit < 0:
        raise ValueError("ct limit must be >= 0")

    start = time.time()
    encoded_query = urllib.parse.quote(f"%.{domain}", safe="")
    url = f"https://crt.sh/?q={encoded_query}&output=json"

    with urllib.request.urlopen(url, timeout=timeout) as resp:
        payload = json.load(resp)
    if not isinstance(payload, list):
        raise ValueError("unexpected crt.sh response shape")

    subdomains, names_seen = _extract_subdomains(payload, domain=domain, limit=limit)
    return (
        subdomains,
        CtFetchSummary(
            records_fetched=len(payload),
            names_seen=names_seen,
            emitted=len(subdomains),
            elapsed_ms=int((time.time() - start) * 1000),
        ),
    )


def subdomains_to_labels(subdomains: Iterable[str], *, domain: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    suffix = f".{domain}"
    for name in subdomains:
        item = str(name).strip().strip(".").lower()
        if item == domain or not item.endswith(suffix):
            continue
        label = item[: -len(suffix)]
        if not label:
            continue
        try:
            normalized = normalize_label(label)
        except ValueError:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        labels.append(normalized)
    return labels


def _extract_subdomains(
    payload: list[Any], *, domain: str, limit: int | None
) -> tuple[list[str], int]:
    subdomains: list[str] = []
    seen: set[str] = set()
    names_seen = 0
    suffix = f".{domain}"

    for row in payload:
        if not isinstance(row, dict):
            continue
        name_value = row.get("name_value")
        if not isinstance(name_value, str):
            continue
        for raw_name in name_value.splitlines():
            name = raw_name.strip().strip(".").lower()
            if not name:
                continue
            names_seen += 1
            if name.startswith("*."):
                name = name[2:]
            if name == domain:
                continue
            if not name.endswith(suffix):
                continue
            try:
                normalize_label(name[: -len(suffix)])
            except ValueError:
                continue
            if name in seen:
                continue
            seen.add(name)
            subdomains.append(name)
            if limit is not None and len(subdomains) >= limit:
                return subdomains, names_seen
    return subdomains, names_seen
