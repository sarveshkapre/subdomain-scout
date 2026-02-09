from __future__ import annotations

import pytest

from subdomain_scout.validation import normalize_domain, normalize_label


def test_normalize_domain_lowercases_and_strips_dots() -> None:
    assert normalize_domain("Example.COM.") == "example.com"


def test_normalize_domain_rejects_single_label() -> None:
    with pytest.raises(ValueError):
        normalize_domain("localhost")


def test_normalize_label_accepts_nested_labels() -> None:
    assert normalize_label("Deep.Api") == "deep.api"


def test_normalize_label_rejects_invalid_chars() -> None:
    with pytest.raises(ValueError):
        normalize_label("bad_name")
