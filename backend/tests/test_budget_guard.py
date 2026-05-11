"""BudgetGuard tests — COST-01 (iter + token caps), COST-02 (daily_spend upsert), COST-03 (payload cap)."""
from __future__ import annotations

import pytest

from app.guards.budget import BudgetExceeded, BudgetGuard


async def test_iter_cap():
    guard = BudgetGuard(
        max_iters=3,
        token_budget=100,
        max_tool_result_bytes=8192,
        db=None,
    )
    for _ in range(3):
        guard.check_iter()
    with pytest.raises(BudgetExceeded) as exc:
        guard.check_iter()
    assert "max_iters=" in str(exc.value)


async def test_token_cap(clean_db, pg_pool):
    guard = BudgetGuard(
        max_iters=100,
        token_budget=100,
        max_tool_result_bytes=8192,
        db=pg_pool,
    )
    # First call uses the full budget; succeeds.
    await guard.record_spend(tokens=100)
    # Next call (cumulative=101 > 100) must raise.
    with pytest.raises(BudgetExceeded) as exc:
        await guard.record_spend(tokens=1)
    assert "token_budget=" in str(exc.value)


async def test_daily_spend_upsert(clean_db, pg_pool):
    guard = BudgetGuard(
        max_iters=100,
        token_budget=10_000,
        max_tool_result_bytes=8192,
        db=pg_pool,
    )
    await guard.record_spend(tokens=500)
    await guard.record_spend(tokens=500)

    rows = await pg_pool.fetch("SELECT date, estimated_tokens, estimated_cost_usd FROM daily_spend")
    assert len(rows) == 1
    row = rows[0]
    assert row["estimated_tokens"] == 1000
    # Haiku input price: $1 per 1M tokens → 1000 tokens = $0.001
    assert float(row["estimated_cost_usd"]) == pytest.approx(0.001, abs=1e-9)


async def test_payload_cap():
    guard = BudgetGuard(
        max_iters=10,
        token_budget=100,
        max_tool_result_bytes=8192,
        db=None,
    )
    guard.check_payload(8192)  # exactly at cap — OK
    with pytest.raises(BudgetExceeded) as exc:
        guard.check_payload(8193)
    assert "8193" in str(exc.value)
