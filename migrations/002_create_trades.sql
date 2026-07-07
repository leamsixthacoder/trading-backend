-- Migration 002: CSV imports + trades
-- Every trade belongs to exactly one account. The UNIQUE constraint on
-- (account_id, external_trade_id) is what makes CSV re-imports safe —
-- re-importing the same file twice, or importing an overlapping date
-- range, cannot create duplicate trades or leak a trade onto the wrong
-- account.

CREATE TYPE import_status AS ENUM ('pending', 'validated', 'failed', 'partial');
CREATE TYPE trade_direction AS ENUM ('long', 'short');

CREATE TABLE csv_imports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL REFERENCES accounts(id),
    source_platform     TEXT NOT NULL,          -- 'lucid_flex', 'topstep', 'ibkr', etc.
    filename            TEXT NOT NULL,
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_count           INTEGER NOT NULL DEFAULT 0,
    rows_inserted       INTEGER NOT NULL DEFAULT 0,
    rows_skipped_dupe   INTEGER NOT NULL DEFAULT 0,
    status              import_status NOT NULL DEFAULT 'pending',
    validation_errors   JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX idx_csv_imports_account ON csv_imports (account_id);

CREATE TABLE trades (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL REFERENCES accounts(id),
    import_batch_id     UUID REFERENCES csv_imports(id),

    source_platform     TEXT NOT NULL,
    external_trade_id   TEXT NOT NULL,          -- broker's own trade/order id, for dedup

    symbol              TEXT NOT NULL,
    direction           trade_direction NOT NULL,
    size                NUMERIC(14,4) NOT NULL CHECK (size > 0),
    entry_price         NUMERIC(14,4) NOT NULL,
    exit_price          NUMERIC(14,4),
    entry_time          TIMESTAMPTZ NOT NULL,
    exit_time           TIMESTAMPTZ,

    fees                NUMERIC(14,4) NOT NULL DEFAULT 0,
    pnl_gross            NUMERIC(14,4),          -- NULL while position open
    pnl_net              NUMERIC(14,4) GENERATED ALWAYS AS (
                             COALESCE(pnl_gross, 0) - fees
                         ) STORED,

    tags                 TEXT[] NOT NULL DEFAULT '{}',
    notes                TEXT,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The core anti-leak guarantee: the same broker trade id can never
    -- be inserted twice under the same account, regardless of how many
    -- times a CSV is imported.
    CONSTRAINT uq_account_external_trade UNIQUE (account_id, external_trade_id),
    CONSTRAINT exit_after_entry CHECK (exit_time IS NULL OR exit_time >= entry_time)
);

CREATE INDEX idx_trades_account ON trades (account_id);
CREATE INDEX idx_trades_account_time ON trades (account_id, entry_time);
CREATE INDEX idx_trades_import_batch ON trades (import_batch_id);

COMMENT ON COLUMN trades.pnl_net IS
    'Always computed, never inserted/updated directly — prevents drift between gross pnl, fees, and net.';
