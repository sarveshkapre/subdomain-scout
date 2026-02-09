from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Fingerprint:
    service: str
    body_substrings: tuple[str, ...]
    status_codes: tuple[int, ...]


@dataclass(frozen=True)
class FingerprintCatalog:
    version: str
    fingerprints: tuple[Fingerprint, ...]


_DEFAULT_CATALOG = FingerprintCatalog(
    version="2026-02-09",
    fingerprints=(
        Fingerprint(
            service="GitHub Pages",
            body_substrings=("there isn't a github pages site here.",),
            status_codes=(404,),
        ),
        Fingerprint(
            service="Heroku",
            body_substrings=("no such app",),
            status_codes=(404,),
        ),
        Fingerprint(
            service="Shopify",
            body_substrings=("sorry, this shop is currently unavailable",),
            status_codes=(402, 403, 404),
        ),
        Fingerprint(
            service="Fastly",
            body_substrings=("fastly error: unknown domain",),
            status_codes=(503,),
        ),
        Fingerprint(
            service="Unbounce",
            body_substrings=("the requested url was not found on this server", "unbounce"),
            status_codes=(404,),
        ),
    ),
)


def build_takeover_checker(
    *, timeout: float, fingerprints_path: Path | None = None
) -> Callable[[str], dict[str, Any] | None]:
    if timeout <= 0:
        raise ValueError("takeover timeout must be > 0")
    catalog = load_fingerprint_catalog(fingerprints_path)

    def check(hostname: str) -> dict[str, Any] | None:
        return detect_takeover(hostname, timeout=timeout, catalog=catalog)

    return check


def load_fingerprint_catalog(path: Path | None) -> FingerprintCatalog:
    if path is None:
        return _DEFAULT_CATALOG

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, dict):
        raise ValueError("takeover fingerprint catalog must be a JSON object")

    version = raw.get("version")
    fingerprints_raw = raw.get("fingerprints")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("takeover fingerprint catalog requires non-empty 'version'")
    if not isinstance(fingerprints_raw, list) or not fingerprints_raw:
        raise ValueError("takeover fingerprint catalog requires non-empty 'fingerprints' list")

    fingerprints: list[Fingerprint] = []
    for idx, item in enumerate(fingerprints_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"fingerprints[{idx}] must be an object")
        service = item.get("service")
        body_substrings_raw = item.get("body_substrings")
        status_codes_raw = item.get("status_codes", [])

        if not isinstance(service, str) or not service.strip():
            raise ValueError(f"fingerprints[{idx}] missing non-empty 'service'")
        if not isinstance(body_substrings_raw, list) or not body_substrings_raw:
            raise ValueError(f"fingerprints[{idx}] missing non-empty 'body_substrings' list")
        body_substrings = tuple(
            str(s).strip().lower()
            for s in body_substrings_raw
            if isinstance(s, str) and str(s).strip()
        )
        if not body_substrings:
            raise ValueError(f"fingerprints[{idx}] has no valid body_substrings")

        if not isinstance(status_codes_raw, list):
            raise ValueError(f"fingerprints[{idx}] 'status_codes' must be a list")
        status_codes: list[int] = []
        for code in status_codes_raw:
            if not isinstance(code, int):
                raise ValueError(f"fingerprints[{idx}] contains non-integer status code")
            status_codes.append(code)

        fingerprints.append(
            Fingerprint(
                service=service.strip(),
                body_substrings=body_substrings,
                status_codes=tuple(status_codes),
            )
        )

    return FingerprintCatalog(version=version.strip(), fingerprints=tuple(fingerprints))


def detect_takeover(
    hostname: str,
    *,
    timeout: float,
    catalog: FingerprintCatalog,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = -1

    for scheme in ("https", "http"):
        url = f"{scheme}://{hostname}/"
        response = _fetch_http_response(url, timeout=timeout)
        if response is None:
            continue

        status_code, body = response
        for fingerprint in catalog.fingerprints:
            score, matched_pattern = _score_fingerprint(
                body=body,
                status_code=status_code,
                fingerprint=fingerprint,
            )
            if score < 50:
                continue
            candidate = {
                "service": fingerprint.service,
                "confidence": _confidence_label(score),
                "score": score,
                "fingerprint_version": catalog.version,
                "matched_pattern": matched_pattern,
                "status_code": status_code,
                "url": url,
            }
            if score > best_score:
                best = candidate
                best_score = score

    return best


def _score_fingerprint(*, body: str, status_code: int, fingerprint: Fingerprint) -> tuple[int, str]:
    matched: list[str] = []
    for pattern in fingerprint.body_substrings:
        if pattern in body:
            matched.append(pattern)

    if not matched:
        return 0, ""

    per_pattern_score = max(20, 70 // len(fingerprint.body_substrings))
    score = min(90, per_pattern_score * len(matched))

    if fingerprint.status_codes and status_code in fingerprint.status_codes:
        score = min(100, score + 20)

    return score, matched[0]


def _confidence_label(score: int) -> str:
    if score >= 90:
        return "high"
    if score >= 70:
        return "medium"
    return "low"


def _fetch_http_response(url: str, *, timeout: float) -> tuple[int, str] | None:
    req = urllib.request.Request(url=url, headers={"User-Agent": "subdomain-scout/0.1.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.getcode())
            body = resp.read(16384).decode("utf-8", errors="ignore").lower()
            return status, body
    except urllib.error.HTTPError as e:
        body = e.read(16384).decode("utf-8", errors="ignore").lower()
        return int(e.code), body
    except (TimeoutError, OSError, urllib.error.URLError):
        return None
