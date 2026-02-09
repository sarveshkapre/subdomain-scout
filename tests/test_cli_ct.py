from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from subdomain_scout.cli import main
from subdomain_scout.ct import CtFetchSummary


def test_ct_command_writes_records_and_summary_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "subdomain_scout.cli.fetch_ct_subdomains",
        lambda _domain, timeout, limit: (
            ["a.example.com", "b.example.com"],
            CtFetchSummary(records_fetched=10, names_seen=12, emitted=2, elapsed_ms=8),
        ),
    )

    rc = main(["ct", "--domain", "Example.COM", "--out", "-", "--summary-json"])
    captured = capsys.readouterr()

    assert rc == 0
    rows = [json.loads(line) for line in captured.out.splitlines()]
    assert [row["subdomain"] for row in rows] == ["a.example.com", "b.example.com"]
    assert all(row["source"] == "crt.sh" for row in rows)
    summary = json.loads(captured.err.strip())
    assert summary["kind"] == "ct_summary"
    assert summary["emitted"] == 2
    assert summary["out"] == "stdout"


def test_scan_with_ct_merges_and_dedupes_labels(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("www\napi\nwww\n", encoding="utf-8")

    monkeypatch.setattr(
        "subdomain_scout.cli.fetch_ct_subdomains",
        lambda _domain, timeout, limit: (
            ["blog.example.com", "www.example.com", "example.com"],
            CtFetchSummary(records_fetched=3, names_seen=3, emitted=2, elapsed_ms=4),
        ),
    )

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name in {"www.example.com", "api.example.com", "blog.example.com"}:
            return [(None, None, None, None, ("1.1.1.1", 0))]
        raise socket.gaierror(getattr(socket, "EAI_NONAME", 8), "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    rc = main(
        [
            "scan",
            "--domain",
            "example.com",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--summary-json",
            "--ct",
            "--timeout",
            "0.1",
            "--concurrency",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    rows = [json.loads(line) for line in captured.out.splitlines()]
    assert {row["subdomain"] for row in rows} == {
        "www.example.com",
        "api.example.com",
        "blog.example.com",
    }
    summary = json.loads(captured.err.strip())
    assert summary["attempted"] == 3
    assert summary["labels_total"] == 5
    assert summary["labels_unique"] == 3
    assert summary["labels_deduped"] == 2
    assert summary["ct_labels"] == 2


def test_scan_rejects_invalid_domain(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["scan", "--domain", "invalid_domain", "--wordlist", "-", "--out", "-"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "domain must contain at least one dot" in captured.err
