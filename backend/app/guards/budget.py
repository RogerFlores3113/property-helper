"""BudgetGuard — cost guardrail enforcement for Phase 1.

Implements:
- COST-01: hard iter cap (`check_iter`) + cumulative token cap (`record_spend`)
- COST-02: daily_spend upsert (one row per calendar date)
- COST-03: per-payload byte cap (`check_payload`)

Limits come from the `settings` singleton (env-driven, D-09/D-10).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..settings import settings

# Open Question #2 resolution: Claude Haiku 4.5 input price is $1 per 1M tokens.
# (Output is $5/M but Phase 1 simulates input-only spend.)
HAIKU_INPUT_USD_PER_TOKEN: float = 1.0 / 1_000_000


class BudgetExceeded(Exception):
    """Raised when any BudgetGuard limit is exceeded."""

    pass


@dataclass
class BudgetGuard:
    max_iters: int
    token_budget: int
    max_tool_result_bytes: int
    db: object  # asyncpg.Pool — untyped to avoid heavy import here
    _iters: int = 0
    _tokens_used: int = 0

    @classmethod
    def from_env(cls, db) -> "BudgetGuard":
        """Construct a BudgetGuard from the settings singleton (D-09)."""
        return cls(
            max_iters=settings.max_iters,
            token_budget=settings.token_budget,
            max_tool_result_bytes=settings.max_tool_result_bytes,
            db=db,
        )

    def check_iter(self) -> None:
        """Increment the iteration counter; raise if over the cap (COST-01)."""
        self._iters += 1
        if self._iters > self.max_iters:
            raise BudgetExceeded(f"max_iters={self.max_iters} exceeded")

    def check_payload(self, num_bytes: int) -> None:
        """Raise if a single tool-result payload exceeds the byte cap (COST-03)."""
        if num_bytes > self.max_tool_result_bytes:
            raise BudgetExceeded(
                f"payload {num_bytes}B > cap {self.max_tool_result_bytes}B"
            )

    async def record_spend(self, tokens: int, cost_usd: float | None = None) -> None:
        """Record simulated LLM spend.

        - Defaults `cost_usd` to Haiku input rate (1e-6 USD/token) when None.
        - Raises BudgetExceeded BEFORE the daily_spend write if the cumulative
          token total would exceed `token_budget` (COST-01).
        - Otherwise upserts daily_spend (COST-02). One row per CURRENT_DATE.
        """
        if cost_usd is None:
            cost_usd = tokens * HAIKU_INPUT_USD_PER_TOKEN

        self._tokens_used += tokens
        if self._tokens_used > self.token_budget:
            raise BudgetExceeded(f"token_budget={self.token_budget} exceeded")

        await self.db.execute(
            """
            INSERT INTO daily_spend (id, date, estimated_tokens, estimated_cost_usd)
            VALUES (gen_random_uuid(), CURRENT_DATE, $1, $2)
            ON CONFLICT (date) DO UPDATE
              SET estimated_tokens = daily_spend.estimated_tokens + EXCLUDED.estimated_tokens,
                  estimated_cost_usd = daily_spend.estimated_cost_usd + EXCLUDED.estimated_cost_usd
            """,
            tokens,
            cost_usd,
        )
