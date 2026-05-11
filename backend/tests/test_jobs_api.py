"""Jobs API tests — implementation lands in Plan 02.

Covers CACH-03 (POST then GET, simulate worker output).
"""
import pytest

pytestmark = pytest.mark.skip(reason="implementation lands in Plan 02")


async def test_fire_and_forget(clean_db, pg_pool, arq_redis):
    ...
