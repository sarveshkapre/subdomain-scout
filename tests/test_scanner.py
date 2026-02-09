from __future__ import annotations

import json
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
    lines = out.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    assert row["attempts"] == 2
    assert row["retries"] == 1


def test_scan_dedupes_labels_and_reports_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name.endswith(".dedupe.test"):
            raise socket.gaierror(getattr(socket, "EAI_NONAME", 8), "not found")
        return [(None, None, None, None, ("8.8.8.8", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    from subdomain_scout.scanner import scan_domains_summary

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("a\na\nb\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"
    summary = scan_domains_summary(
        domain="dedupe.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
    )

    assert summary.attempted == 2
    assert summary.labels_total == 3
    assert summary.labels_unique == 2
    assert summary.labels_deduped == 1


def test_scan_takeover_checker_updates_summary_and_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name == "a.takeover.test":
            return [(None, None, None, None, ("1.1.1.1", 0))]
        raise socket.gaierror(getattr(socket, "EAI_NONAME", 8), "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    from subdomain_scout.scanner import scan_domains_summary

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("a\nb\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"

    summary = scan_domains_summary(
        domain="takeover.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
        takeover_checker=lambda host: (
            {
                "service": "Heroku",
                "confidence": "high",
                "score": 90,
                "fingerprint_version": "test-v1",
                "matched_pattern": "no such app",
                "status_code": 404,
                "url": f"https://{host}/",
            }
            if host == "a.takeover.test"
            else None
        ),
    )

    assert summary.takeover_checked == 1
    assert summary.takeover_suspected == 1
    lines = out.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert first["subdomain"] == "a.takeover.test"
    assert first["takeover"]["service"] == "Heroku"
