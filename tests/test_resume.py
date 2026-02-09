from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from subdomain_scout.scanner import scan_domains_summary


def test_scan_resume_skips_existing_and_appends(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_getaddrinfo(name: str, _port: object) -> list[tuple[object, ...]]:
        return [(None, None, None, None, ("8.8.8.8", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    out = tmp_path / "out.jsonl"
    out.write_text(
        json.dumps(
            {
                "subdomain": "a.resume.test",
                "ips": ["8.8.8.8"],
                "status": "resolved",
                "elapsed_ms": 1,
                "attempts": 1,
                "retries": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("a\nb\n", encoding="utf-8")

    summary = scan_domains_summary(
        domain="resume.test",
        wordlist=wordlist,
        out_path=out,
        timeout=0.1,
        concurrency=1,
        resume=True,
    )

    assert summary.attempted == 1
    assert summary.labels_total == 2
    assert summary.labels_unique == 2
    assert summary.labels_skipped_existing == 1

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["subdomain"] == "a.resume.test"
    assert json.loads(lines[1])["subdomain"] == "b.resume.test"
