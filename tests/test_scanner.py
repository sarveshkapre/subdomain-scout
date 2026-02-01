from __future__ import annotations

import socket
from pathlib import Path

import pytest

from subdomain_scout.scanner import scan_domains


def test_scan_writes_report(tmp_path: Path) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("example\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"
    scan_domains("invalid.test", wordlist, out, timeout=0.1)
    assert out.exists()


def test_scan_retries_transient_dns_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, int] = {}

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        calls[name] = calls.get(name, 0) + 1
        if name == "a.retry.test" and calls[name] == 1:
            raise socket.gaierror(getattr(socket, "EAI_AGAIN", 2), "try again")
        if name == "a.retry.test":
            return [(None, None, None, None, ("8.8.8.8", 0))]
        raise socket.gaierror(getattr(socket, "EAI_NONAME", 8), "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    from subdomain_scout.scanner import scan_domains_summary

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("a\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"

    summary = scan_domains_summary(
        domain="retry.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
        retries=1,
        retry_backoff_ms=0,
        statuses={"resolved"},
    )
    assert summary.attempted == 1
    assert summary.resolved == 1
    assert summary.error == 0
    assert calls["a.retry.test"] == 2
