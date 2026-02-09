from __future__ import annotations

import re

_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_domain(raw: str) -> str:
    domain = str(raw).strip().strip(".").lower()
    if not domain:
        raise ValueError("domain must be non-empty")
    _validate_hostname(domain, allow_single_label=False, value_name="domain")
    return domain


def normalize_label(raw: str) -> str:
    label = str(raw).strip().strip(".").lower()
    if not label:
        raise ValueError("label must be non-empty")
    _validate_hostname(label, allow_single_label=True, value_name="label")
    return label


def _validate_hostname(value: str, *, allow_single_label: bool, value_name: str) -> None:
    if len(value) > 253:
        raise ValueError(f"{value_name} is too long (max 253 characters)")

    parts = value.split(".")
    if not allow_single_label and len(parts) < 2:
        raise ValueError(f"{value_name} must contain at least one dot")
    for part in parts:
        if not _LABEL_RE.match(part):
            raise ValueError(f"invalid {value_name}: {value!r}")
