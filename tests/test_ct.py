from __future__ import annotations

import io
import json
import urllib.request

import pytest

from subdomain_scout.ct import fetch_ct_subdomains, subdomains_to_labels


class _FakeResponse(io.BytesIO):
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()


def test_fetch_ct_subdomains_parses_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {"name_value": "*.a.example.com\nb.example.com\nexample.com\nbad_name.example.com"},
        {"name_value": "b.example.com\nc.example.com"},
        {"name_value": "x.other.com"},
    ]
    called: dict[str, object] = {}

    def fake_urlopen(url: str, timeout: float) -> _FakeResponse:
        called["url"] = url
        called["timeout"] = timeout
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    subdomains, summary = fetch_ct_subdomains("example.com", timeout=4.0, limit=None)

    assert called["url"] == "https://crt.sh/?q=%25.example.com&output=json"
    assert called["timeout"] == 4.0
    assert subdomains == ["a.example.com", "b.example.com", "c.example.com"]
    assert summary.records_fetched == 3
    assert summary.names_seen == 7
    assert summary.emitted == 3


def test_fetch_ct_subdomains_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"name_value": "a.example.com\nb.example.com\nc.example.com"}]
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda _url, timeout: _FakeResponse(json.dumps(payload).encode("utf-8")),
    )

    subdomains, summary = fetch_ct_subdomains("example.com", timeout=2.0, limit=2)
    assert subdomains == ["a.example.com", "b.example.com"]
    assert summary.emitted == 2


def test_subdomains_to_labels_filters_apex_and_dedupes() -> None:
    labels = subdomains_to_labels(
        ["www.example.com", "deep.api.example.com", "example.com", "www.example.com"],
        domain="example.com",
    )
    assert labels == ["www", "deep.api"]
