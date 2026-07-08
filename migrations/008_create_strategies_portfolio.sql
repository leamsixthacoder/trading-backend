-- Migration 008: Phase 3 — strategy development/testing (Track A) and
-- stock portfolio management (Track B). Two independent tracks, no changes
-- to existing schema.

-- ============================================================
-- Track A: Strategy Development & Testing
-- ============================================================

CREATE TABLE strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    rules           JSONB NOT NULL,   -- entry/exit/sizing rules, structure is strategy-specific
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'backtesting', 'validated', 'live', 'retired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Position sizing rules, referenced by strategy and/or account.
CREATE TABLE position_sizing_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID REFERENCES strategies(id),
    account_id      UUID REFERENCES accounts(id),   -- nullable: some sizing rules are strategy-wide
    method          TEXT NOT NULL,   -- 'fixed', 'pct_of_balance', 'volatility_adjusted'
    parameters      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per backtest RUN, not per trade. Runs against the user's own
-- trades filtered by tag/setup + period (no external market data source).
CREATE TABLE backtests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         UUID NOT NULL REFERENCES strategies(id),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    data_source         TEXT NOT NULL,   -- what data the backtest ran against, e.g. 'own_trades:breakout'
    total_trades        INTEGER NOT NULL,
    win_rate            NUMERIC(5,4),
    total_pnl           NUMERIC(14,2),
    max_drawdown        NUMERIC(14,2),
    sharpe_ratio        NUMERIC(8,4),
    parameters_snapshot JSONB NOT NULL,   -- full strategy+sizing config used, for reproducibility
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The explicit gate between "backtested" and "allowed on a real account."
-- Enforced at the API layer: PATCH /strategies/{id} refuses a transition to
-- status='live' without an approved row here.
CREATE TABLE strategy_validations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID NOT NULL REFERENCES strategies(id),
    backtest_id     UUID NOT NULL REFERENCES backtests(id),
    approved        BOOLEAN NOT NULL,
    criteria_met    JSONB NOT NULL,   -- which validation criteria passed/failed and why
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Track B: Portfolio Management (stock accounts)
-- ============================================================

-- Reuses accounts.account_type = 'personal_portfolio' from Phase 1 — no new
-- account concept, just a new kind of position within it.
CREATE TABLE holdings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),  -- must be a personal_portfolio account
    symbol          TEXT NOT NULL,
    quantity        NUMERIC(14,4) NOT NULL,
    cost_basis      NUMERIC(14,4) NOT NULL,   -- average cost per share
    acquired_date   DATE NOT NULL,
    asset_class     TEXT NOT NULL DEFAULT 'equity',  -- 'equity', 'etf', 'bond', etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_holdings_account ON holdings (account_id);

-- Point-in-time portfolio value snapshots, needed for period returns.
-- Prices/values are supplied at capture time — no live price-feed
-- dependency. Computing accurate long-window returns requires having
-- captured values along the way; this table cannot be backfilled later.
CREATE TABLE portfolio_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    snapshot_date   DATE NOT NULL,
    total_value     NUMERIC(14,2) NOT NULL,
    holdings_detail JSONB NOT NULL,   -- snapshot of holdings + prices at this date
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, snapshot_date)
);
