-- Migration 003: Allocations ledger (append-only)
-- This table is never UPDATEd and never DELETEd from the application
-- layer (enforced by trigger below). Every payout, profit share, or
-- reserve movement is a new row. This is what gives you a full audit
-- trail for free: nothing overwrites history.

CREATE TYPE allocation_type AS ENUM (
    'profit_share',
    'payout',
    'reserve',
    'reinvestment',
    'correction'      -- explicit, visible correcting entry — never edit old rows
);

CREATE TABLE allocations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    type            allocation_type NOT NULL,
    amount          NUMERIC(14,2) NOT NULL,   -- signed: negative for payouts/withdrawals
    period_start    DATE,
    period_end      DATE,
    computed_from   JSONB NOT NULL DEFAULT '{}'::jsonb,  -- snapshot: trade ids / sums used
    memo            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT NOT NULL DEFAULT 'system'
);

CREATE INDEX idx_allocations_account ON allocations (account_id, created_at);

-- Enforce append-only at the database level, not just convention.
CREATE OR REPLACE FUNCTION reject_allocation_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'allocations is append-only: % not permitted. Insert a correction row instead.', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_allocations_no_update
    BEFORE UPDATE ON allocations
    FOR EACH ROW EXECUTE FUNCTION reject_allocation_mutation();

CREATE TRIGGER trg_allocations_no_delete
    BEFORE DELETE ON allocations
    FOR EACH ROW EXECUTE FUNCTION reject_allocation_mutation();

COMMENT ON TABLE allocations IS
    'Append-only ledger. Balance is SUM(trades.pnl_net) + SUM(allocations.amount) per account — see 004_views.sql. Fix mistakes with a correction row, never an UPDATE.';
