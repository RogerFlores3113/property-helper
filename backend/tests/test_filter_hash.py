"""RED — compute_filter_hash (CACH-01).

Covers decisions:
  - D-01 (05-CONTEXT): filter_hash is SHA-256 over canonical chips, ignoring flex
        and chip ordering, so cache-equivalent searches collide deterministically.
  - Pitfall 6 (05-CONTEXT): flex toggles do NOT change the filter_hash — flex
        affects ranking, not the cache key.

This file deliberately imports a module that does not exist yet
(app.workers.cache). The ImportError IS the RED signal — plan 05-02 will
create the module and turn these tests GREEN.
"""
from __future__ import annotations

import re

import pytest

from app.workers.cache import compute_filter_hash  # noqa: F401 — RED import

pytestmark = pytest.mark.red_phase_05


def test_compute_filter_hash_deterministic_across_chip_order():
    chips_a = [
        {"id": "1", "type": "beds", "value": 2, "flex": False},
        {"id": "2", "type": "max_price", "value": 5000, "flex": False},
    ]
    chips_b = [
        {"id": "2", "type": "max_price", "value": 5000, "flex": False},
        {"id": "1", "type": "beds", "value": 2, "flex": False},
    ]
    assert compute_filter_hash(chips_a) == compute_filter_hash(chips_b)


def test_compute_filter_hash_ignores_flex():
    chips_strict = [{"id": "1", "type": "beds", "value": 2, "flex": False}]
    chips_flex = [{"id": "1", "type": "beds", "value": 2, "flex": True}]
    assert compute_filter_hash(chips_strict) == compute_filter_hash(chips_flex)


def test_compute_filter_hash_hex_format():
    chips = [{"id": "1", "type": "beds", "value": 2, "flex": False}]
    digest = compute_filter_hash(chips)
    assert re.match(r"^[0-9a-f]{64}$", digest), f"not a sha256 hex digest: {digest!r}"


def test_compute_filter_hash_empty_chips():
    digest = compute_filter_hash([])
    assert re.match(r"^[0-9a-f]{64}$", digest)
    # Stability check — empty list always hashes the same.
    assert compute_filter_hash([]) == digest
