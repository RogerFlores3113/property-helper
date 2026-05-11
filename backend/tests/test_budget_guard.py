"""BudgetGuard tests — implementation lands in Plan 02.

Covers COST-01 (iter + token caps), COST-02 (daily_spend upsert), COST-03 (payload cap).
"""
import pytest

pytestmark = pytest.mark.skip(reason="implementation lands in Plan 02")


async def test_iter_cap():
    ...


async def test_token_cap(clean_db, pg_pool):
    ...


async def test_daily_spend_upsert(clean_db, pg_pool):
    ...


async def test_payload_cap():
    ...
