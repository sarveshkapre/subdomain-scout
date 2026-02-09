from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from subdomain_scout.cli import main


def test_scan_takeover_check_wires_checker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("www\n", encoding="utf-8")

    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        if name == "www.example.com":
            return [(None, None, None, None, ("1.1.1.1", 0))]
        raise socket.gaierror(getattr(socket, "EAI_NONAME", 8), "not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        "subdomain_scout.cli.build_takeover_checker",
        lambda timeout, fingerprints_path: (
            lambda host: {
                "service": "GitHub Pages",
                "confidence": "high",
                "score": 90,
                "fingerprint_version": "test-v1",
                "matched_pattern": "there isn't a github pages site here.",
                "status_code": 404,
                "url": f"https://{host}/",
            }
        ),
    )

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
            "--takeover-check",
            "--timeout",
            "0.1",
            "--concurrency",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    rows = [json.loads(line) for line in captured.out.splitlines()]
    assert rows[0]["takeover"]["service"] == "GitHub Pages"
    summary = json.loads(captured.err.strip())
    assert summary["takeover_checked"] == 1
    assert summary["takeover_suspected"] == 1


def test_scan_takeover_check_rejects_missing_fingerprint_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "scan",
            "--domain",
            "example.com",
            "--wordlist",
            "-",
            "--out",
            "-",
            "--takeover-check",
            "--takeover-fingerprints",
            "missing.json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "file not found" in captured.err.lower()
