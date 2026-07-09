-- Migration 010: account_rules — per-account prop-firm thresholds
-- (Profit Target, Daily Loss Limit, Max Loss Limit), shown on the Account
-- Detail Rules row for funded/eval accounts (FRONTEND_SPEC.md §4).
--
-- CRU only, deliberately no DELETE endpoint: a threshold is corrected via
-- PATCH (which bumps updated_at), not removed, so "what was this account's
-- limit as of date X" stays answerable from created_at/updated_at rather
-- than being silently lost like an overwritten value would be.

CREATE TYPE account_rule_type AS ENUM ('profit_target', 'daily_loss_limit', 'max_loss_limit');

CREATE TABLE account_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    rule_type       account_rule_type NOT NULL,
    threshold       NUMERIC(14,2) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One threshold per type per account — PATCH the existing row to
    -- change it rather than inserting a second one.
    CONSTRAINT uq_account_rules_account_type UNIQUE (account_id, rule_type)
);

CREATE INDEX idx_account_rules_account ON account_rules (account_id);
