-- Migration 001: Accounts table
-- Accounts are the root separation boundary. Every trade and allocation
-- must reference exactly one account_id. Nothing about an account's
-- balance is ever stored directly here — balances are always derived
-- from trades + allocations (see 003_views.sql).

CREATE TYPE account_type AS ENUM (
    'funded_lucid',
    'funded_topstep',
    'personal_live',
    'personal_portfolio'
);

CREATE TYPE account_status AS ENUM (
    'active',
    'paused',
    'failed',
    'closed'
);

CREATE TABLE accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label           TEXT NOT NULL,              -- human name, e.g. "Lucid Flex #3"
    account_type    account_type NOT NULL,
    provider        TEXT,                       -- 'lucid_flex', 'topstep', NULL for personal
    capital_base    NUMERIC(14,2) NOT NULL CHECK (capital_base > 0),
    status          account_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,

    CONSTRAINT closed_at_requires_closed_status
        CHECK (closed_at IS NULL OR status = 'closed')
);

CREATE INDEX idx_accounts_type_status ON accounts (account_type, status);

COMMENT ON TABLE accounts IS
    'Root entity for account separation. All trades and allocations FK to this. Never mutate a stored balance field here — there isn''t one on purpose.';

-- Status changes (active -> failed, active -> closed, a reset, etc.) are
-- recorded automatically by trigger, not by application code remembering to
-- log it. This answers "when did this account fail?" without relying on
-- discipline elsewhere.
CREATE TABLE account_status_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    old_status      account_status,       -- NULL on the row created at account creation
    new_status      account_status NOT NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    memo            TEXT
);

CREATE INDEX idx_account_status_history_account ON account_status_history (account_id, changed_at);

CREATE OR REPLACE FUNCTION log_account_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO account_status_history (account_id, old_status, new_status)
        VALUES (NEW.id, NULL, NEW.status);
    ELSIF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO account_status_history (account_id, old_status, new_status)
        VALUES (NEW.id, OLD.status, NEW.status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_accounts_log_status_insert
    AFTER INSERT ON accounts
    FOR EACH ROW EXECUTE FUNCTION log_account_status_change();

CREATE TRIGGER trg_accounts_log_status_update
    AFTER UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION log_account_status_change();

COMMENT ON TABLE account_status_history IS
    'Auto-populated by trigger on every accounts.status change (including creation). Never insert into this table directly from application code.';
