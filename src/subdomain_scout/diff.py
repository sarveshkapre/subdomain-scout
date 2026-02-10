from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO


@dataclass(frozen=True)
class RecordView:
    status: str
    ips: list[str]
    cnames: list[str]
    error: str | None

    @classmethod
    def from_obj(cls, obj: dict[str, Any]) -> RecordView:
        status = str(obj.get("status", ""))
        ips_raw = obj.get("ips", [])
        ips = [str(x) for x in ips_raw] if isinstance(ips_raw, list) else []
        cnames_raw = obj.get("cnames", [])
        cnames = [str(x) for x in cnames_raw] if isinstance(cnames_raw, list) else []
        err_raw = obj.get("error", None)
        error = None if err_raw is None else str(err_raw)
        return cls(status=status, ips=ips, cnames=cnames, error=error)

    def stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status, "ips": self.ips}
        if self.cnames:
            payload["cnames"] = self.cnames
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class DiffSummary:
    old_total: int
    new_total: int
    added: int
    removed: int
    changed: int
    unchanged: int


def load_jsonl(
    stream: IO[str],
    *,
    src: str,
    resolved_only: bool,
    skip_invalid: bool,
) -> dict[str, RecordView]:
    records: dict[str, RecordView] = {}
    for lineno, raw in enumerate(stream, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            if skip_invalid:
                continue
            raise ValueError(f"{src}:{lineno}: invalid JSON: {e}") from e
        if not isinstance(obj, dict):
            if skip_invalid:
                continue
            raise ValueError(f"{src}:{lineno}: expected JSON object per line")

        subdomain_raw = obj.get("subdomain", None)
        if not isinstance(subdomain_raw, str) or not subdomain_raw.strip():
            if skip_invalid:
                continue
            raise ValueError(f"{src}:{lineno}: missing/invalid 'subdomain'")

        view = RecordView.from_obj(obj)
        if resolved_only and view.status != "resolved":
            continue
        records[subdomain_raw.strip().lower()] = view
    return records


def compute_diff(
    old: dict[str, RecordView],
    new: dict[str, RecordView],
) -> tuple[DiffSummary, list[dict[str, Any]]]:
    added = 0
    removed = 0
    changed = 0
    unchanged = 0
    events: list[dict[str, Any]] = []

    all_keys = sorted(set(old) | set(new))
    for key in all_keys:
        o = old.get(key)
        n = new.get(key)
        if o is None and n is not None:
            added += 1
            events.append({"kind": "added", "subdomain": key, "new": n.stable_dict()})
            continue
        if o is not None and n is None:
            removed += 1
            events.append({"kind": "removed", "subdomain": key, "old": o.stable_dict()})
            continue
        if o is None or n is None:
            continue

        if o.stable_dict() == n.stable_dict():
            unchanged += 1
            continue

        changed += 1
        events.append(
            {
                "kind": "changed",
                "subdomain": key,
                "old": o.stable_dict(),
                "new": n.stable_dict(),
            }
        )

    summary = DiffSummary(
        old_total=len(old),
        new_total=len(new),
        added=added,
        removed=removed,
        changed=changed,
        unchanged=unchanged,
    )
    return summary, events


def open_path(path: str) -> Path | None:
    return None if path == "-" else Path(path)
