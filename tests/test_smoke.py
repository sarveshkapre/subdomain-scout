from __future__ import annotations

import subprocess
import sys


def test_help() -> None:
    proc = subprocess.run([sys.executable, "-m", "subdomain_scout", "--help"], check=False)
    assert proc.returncode == 0
