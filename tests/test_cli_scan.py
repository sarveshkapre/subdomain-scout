from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_scan_stdout_does_not_include_summary(tmp_path: Path) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("www\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "invalid.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--only-resolved",
            "--timeout",
            "0.1",
            "--concurrency",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert "scanned attempted=1" in proc.stderr


def test_scan_summary_json_is_parseable(tmp_path: Path) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("www\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "invalid.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--summary-json",
            "--only-resolved",
            "--timeout",
            "0.1",
            "--concurrency",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stderr.strip())
    assert payload["kind"] == "scan_summary"
    assert payload["attempted"] == 1
    assert payload["out"] == "stdout"


def test_scan_supports_wordlist_stdin(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "invalid.test",
            "--wordlist",
            "-",
            "--out",
            "-",
            "--summary-json",
            "--only-resolved",
            "--timeout",
            "0.1",
            "--concurrency",
            "1",
        ],
        input="www\n",
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    payload = json.loads(proc.stderr.strip())
    assert payload["attempted"] == 1
