"""Stub scraper tests — implementation lands in Plan 02.

Covers CACH-04 (payload size 300-500 chars) and skeleton smoke (9 listings + completed).
"""
import pytest

pytestmark = pytest.mark.skip(reason="implementation lands in Plan 02")


async def test_payload_size():
    ...


async def test_run_search(clean_db, pg_pool, arq_redis):
    ...
