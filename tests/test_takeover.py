from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import pytest

from subdomain_scout.takeover import (
    build_takeover_checker,
    load_fingerprint_catalog,
)


class _FakeResponse(io.BytesIO):
    def __init__(self, body: str, *, status: int) -> None:
        super().__init__(body.encode("utf-8"))
        self._status = status

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()

    def getcode(self) -> int:
        return self._status


def test_takeover_checker_matches_default_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        assert req.full_url in {
            "https://dangling.example.com/",
            "http://dangling.example.com/",
        }
        assert timeout == 2.0
        return _FakeResponse("There isn't a GitHub Pages site here.", status=404)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    checker = build_takeover_checker(timeout=2.0)
    match = checker("dangling.example.com")

    assert match is not None
    assert match["service"] == "GitHub Pages"
    assert match["confidence"] == "high"
    assert match["score"] == 90
    assert match["fingerprint_version"] == "2026-02-09"


def test_takeover_checker_returns_none_for_non_matching_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda _req, timeout: _FakeResponse("ok", status=200),
    )

    checker = build_takeover_checker(timeout=1.0)
    assert checker("safe.example.com") is None


def test_load_fingerprint_catalog_supports_custom_file(tmp_path: Path) -> None:
    raw = {
        "version": "2026-02-10",
        "fingerprints": [
            {
                "service": "Custom CDN",
                "body_substrings": ["custom dangling hostname"],
                "status_codes": [404],
            }
        ],
    }
    path = tmp_path / "fingerprints.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    catalog = load_fingerprint_catalog(path)
    assert catalog.version == "2026-02-10"
    assert len(catalog.fingerprints) == 1
    assert catalog.fingerprints[0].service == "Custom CDN"


def test_load_fingerprint_catalog_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"fingerprints": []}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_fingerprint_catalog(path)
