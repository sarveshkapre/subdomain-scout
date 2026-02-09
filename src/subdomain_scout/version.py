from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path


def get_version() -> str:
    """
    Return the package version.

    Prefer installed package metadata. When running from a source checkout without an
    editable install, fall back to parsing `pyproject.toml`.
    """
    # Prefer source checkout version if available, so editable installs don't drift
    # when `pyproject.toml` changes without reinstalling.
    guessed = _read_pyproject_version(_repo_root())
    if guessed:
        return guessed

    try:
        return metadata.version("subdomain-scout")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_pyproject_version(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None

    in_project = False
    version_re = re.compile(r'^version\s*=\s*"([^"]+)"\s*$')
    for raw in pyproject.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if not in_project:
            continue
        m = version_re.match(line)
        if m:
            return m.group(1).strip()
    return None
