from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _pyproject_version() -> str:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    in_project = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if not in_project:
            continue
        m = re.match(r'^version\s*=\s*"([^"]+)"\s*$', line)
        if m:
            return m.group(1)
    raise AssertionError("failed to locate [project].version in pyproject.toml")


def test_cli_version_matches_pyproject() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "subdomain_scout", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == _pyproject_version()
