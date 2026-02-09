from __future__ import annotations

import socket
from pathlib import Path

import pytest

from subdomain_scout.scanner import detect_wildcard_ips, scan_domains_summary


def test_detect_wildcard_ips_returns_ipset(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = iter(["aaaa", "bbbb"])
    monkeypatch.setattr("subdomain_scout.scanner.secrets.token_hex", lambda _n: next(tokens))

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name.endswith(".wild.test"):
            return [(None, None, None, None, ("9.9.9.9", 0))]
        raise socket.gaierror(socket.EAI_NONAME, "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert detect_wildcard_ips("wild.test", probes=2) == {"9.9.9.9"}


def test_scan_marks_wildcard_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tokens = iter(["aaaa", "bbbb"])
    monkeypatch.setattr("subdomain_scout.scanner.secrets.token_hex", lambda _n: next(tokens))

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name == "real.wild.test":
            return [(None, None, None, None, ("1.1.1.1", 0))]
        if name.endswith(".wild.test"):
            return [(None, None, None, None, ("9.9.9.9", 0))]
        raise socket.gaierror(socket.EAI_NONAME, "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("foo\nreal\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"

    summary = scan_domains_summary(
        domain="wild.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
        detect_wildcard=True,
        wildcard_probes=2,
        only_resolved=False,
    )

    assert summary.attempted == 2
    assert summary.wildcard == 1
    assert summary.resolved == 1

    lines = out.read_text(encoding="utf-8").splitlines()
    assert any(
        '"subdomain": "foo.wild.test"' in line and '"status": "wildcard"' in line for line in lines
    )
    assert any(
        '"subdomain": "real.wild.test"' in line and '"status": "resolved"' in line for line in lines
    )


def test_scan_marks_multilevel_wildcard_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Root does not wildcard, but "*.dev.wild.test" does.
    tokens = iter(["aaaa", "bbbb"])
    monkeypatch.setattr("subdomain_scout.scanner.secrets.token_hex", lambda _n: next(tokens))

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name == "real.dev.wild.test":
            return [(None, None, None, None, ("1.1.1.1", 0))]
        if name.endswith(".dev.wild.test"):
            return [(None, None, None, None, ("9.9.9.9", 0))]
        raise socket.gaierror(socket.EAI_NONAME, "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("foo.dev\nreal.dev\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"

    summary = scan_domains_summary(
        domain="wild.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
        detect_wildcard=True,
        wildcard_probes=2,
        only_resolved=False,
    )

    assert summary.attempted == 2
    assert summary.wildcard == 1
    assert summary.resolved == 1

    lines = out.read_text(encoding="utf-8").splitlines()
    assert any(
        '"subdomain": "foo.dev.wild.test"' in line and '"status": "wildcard"' in line
        for line in lines
    )
    assert any(
        '"subdomain": "real.dev.wild.test"' in line and '"status": "resolved"' in line
        for line in lines
    )


def test_scan_wildcard_http_verification_can_flip_false_positive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Simulate CDN behavior where wildcard and a real host share the same IP-set.
    tokens = iter(
        [
            "aaaaaaaaaaaaaaaa",
            "bbbbbbbbbbbbbbbb",
            "cccccccccccccccc",
        ]
    )
    monkeypatch.setattr("subdomain_scout.scanner.secrets.token_hex", lambda _n: next(tokens))

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name.endswith(".wild.test"):
            return [(None, None, None, None, ("9.9.9.9", 0))]
        raise socket.gaierror(socket.EAI_NONAME, "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    class _Resp:
        def __init__(self, status: int, body: str) -> None:
            self._status = status
            self._body = body

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
            return None

        def getcode(self) -> int:
            return self._status

        def read(self, _n: int) -> bytes:
            return self._body.encode("utf-8")

    def fake_urlopen(req: object, timeout: float) -> _Resp:
        # urllib hands us a Request; use the URL string for host switching.
        url = getattr(req, "full_url", str(req))
        if "real.wild.test" in url:
            return _Resp(200, "welcome to the real site")
        # Wildcard landing page that echoes the hostname.
        return _Resp(404, f"not found for {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("foo\nreal\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"

    summary = scan_domains_summary(
        domain="wild.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
        detect_wildcard=True,
        wildcard_probes=2,
        wildcard_threshold=1,
        wildcard_verify_http=True,
        wildcard_http_timeout=0.1,
        only_resolved=False,
    )

    assert summary.attempted == 2
    assert summary.wildcard == 1
    assert summary.resolved == 1

    lines = out.read_text(encoding="utf-8").splitlines()
    assert any(
        '"subdomain": "foo.wild.test"' in line and '"status": "wildcard"' in line for line in lines
    )
    assert any(
        '"subdomain": "real.wild.test"' in line and '"status": "resolved"' in line for line in lines
    )
