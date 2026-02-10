from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_diff_emits_expected_kinds(tmp_path: Path) -> None:
    old_path = tmp_path / "old.jsonl"
    new_path = tmp_path / "new.jsonl"

    old_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"subdomain": "a.example.com", "status": "resolved", "ips": ["1.1.1.1"]}
                ),
                json.dumps({"subdomain": "b.example.com", "status": "not_found", "ips": []}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    new_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"subdomain": "a.example.com", "status": "resolved", "ips": ["2.2.2.2"]}
                ),
                json.dumps({"subdomain": "b.example.com", "status": "not_found", "ips": []}),
                json.dumps(
                    {"subdomain": "c.example.com", "status": "resolved", "ips": ["3.3.3.3"]}
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "diff",
            "--old",
            str(old_path),
            "--new",
            str(new_path),
            "--resolved-only",
            "--only",
            "added",
            "--only",
            "changed",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0

    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert {e["kind"] for e in events} == {"added", "changed"}
    assert {e["subdomain"] for e in events} == {"a.example.com", "c.example.com"}
    assert "diff old=1 new=2 added=1 removed=0 changed=1 unchanged=0" in proc.stderr


def test_diff_summary_only_writes_no_stdout(tmp_path: Path) -> None:
    old_path = tmp_path / "old.jsonl"
    new_path = tmp_path / "new.jsonl"
    old_path.write_text(
        json.dumps({"subdomain": "a.example.com", "status": "resolved", "ips": []}) + "\n"
    )
    new_path.write_text(
        json.dumps({"subdomain": "a.example.com", "status": "resolved", "ips": []}) + "\n"
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "diff",
            "--old",
            str(old_path),
            "--new",
            str(new_path),
            "--summary-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert "diff old=1 new=1 added=0 removed=0 changed=0 unchanged=1" in proc.stderr


def test_diff_summary_json_is_parseable(tmp_path: Path) -> None:
    old_path = tmp_path / "old.jsonl"
    new_path = tmp_path / "new.jsonl"
    old_path.write_text(
        json.dumps({"subdomain": "a.example.com", "status": "resolved", "ips": []}) + "\n"
    )
    new_path.write_text(
        "\n".join(
            [
                json.dumps({"subdomain": "a.example.com", "status": "resolved", "ips": []}),
                json.dumps(
                    {"subdomain": "b.example.com", "status": "resolved", "ips": ["1.1.1.1"]}
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "diff",
            "--old",
            str(old_path),
            "--new",
            str(new_path),
            "--summary-only",
            "--summary-json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    payload = json.loads(proc.stderr.strip())
    assert payload["kind"] == "diff_summary"
    assert payload["schema_version"] == 1
    assert payload["added"] == 1


def test_diff_includes_cnames_when_present(tmp_path: Path) -> None:
    old_path = tmp_path / "old.jsonl"
    new_path = tmp_path / "new.jsonl"

    old_path.write_text(
        json.dumps(
            {
                "subdomain": "a.example.com",
                "status": "resolved",
                "ips": ["1.1.1.1"],
                "cnames": ["old.target.example.com"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    new_path.write_text(
        json.dumps(
            {
                "subdomain": "a.example.com",
                "status": "resolved",
                "ips": ["1.1.1.1"],
                "cnames": ["new.target.example.com"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "diff",
            "--old",
            str(old_path),
            "--new",
            str(new_path),
            "--only",
            "changed",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(events) == 1
    assert events[0]["kind"] == "changed"
    assert events[0]["subdomain"] == "a.example.com"
    assert events[0]["old"]["cnames"] == ["old.target.example.com"]
    assert events[0]["new"]["cnames"] == ["new.target.example.com"]
