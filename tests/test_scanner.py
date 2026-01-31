from __future__ import annotations

from pathlib import Path

from subdomain_scout.scanner import scan_domains


def test_scan_writes_report(tmp_path: Path) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("example\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"
    scan_domains("invalid.test", wordlist, out, timeout=0.1)
    assert out.exists()
