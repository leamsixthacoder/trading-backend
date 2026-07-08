-- Migration 007: Phase 2 — journal, risk rules/alerts, setup/hour analytics
-- Nothing in Phase 1's schema changes. Risk alerts are surfaced, not
-- enforced: this schema only supports detection + acknowledgement, never
-- blocking a trade or auto-flattening a position.

CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID REFERENCES accounts(id),   -- nullable: some entries are cross-account
    entry_date      DATE NOT NULL,
    entry_type      TEXT NOT NULL CHECK (entry_type IN ('daily_log', 'meeting_note', 'general')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_journal_entries_date ON journal_entries (entry_date);

-- Risk rule definitions — what counts as a "deviation" per account or globally.
CREATE TABLE risk_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID REFERENCES accounts(id),   -- NULL = applies to all accounts
    rule_type       TEXT NOT NULL,   -- e.g. 'max_daily_loss', 'max_position_size', 'max_trades_per_day'
    threshold       NUMERIC(14,2) NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Alerts generated when a risk rule is breached — computed by
-- scripts/evaluate_risk.py, not manually entered. Never dedupe: each
-- evaluation run that finds a breach inserts a new row, so history is
-- preserved same as the allocations ledger.
CREATE TABLE risk_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    risk_rule_id    UUID NOT NULL REFERENCES risk_rules(id),
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    actual_value    NUMERIC(14,2) NOT NULL,
    threshold_value NUMERIC(14,2) NOT NULL,
    acknowledged    BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_risk_alerts_account ON risk_alerts (account_id, triggered_at);

-- Per-setup performance. Filtered on exit_time (realized/closed trades only,
-- same convention as account_pnl_by_day/_by_month) rather than pnl_net,
-- which is a GENERATED STORED column and is never NULL.
CREATE VIEW pnl_by_setup AS
SELECT
    account_id,
    UNNEST(tags) AS setup_tag,
    SUM(pnl_net) AS total_pnl,
    COUNT(*) AS trade_count,
    AVG(pnl_net) AS avg_pnl,
    SUM(CASE WHEN pnl_net > 0 THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) AS win_rate
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY account_id, UNNEST(tags);

-- Time-of-day performance, same closed-trades convention as above.
CREATE VIEW pnl_by_hour_of_day AS
SELECT
    account_id,
    EXTRACT(HOUR FROM entry_time) AS hour_of_day,
    SUM(pnl_net) AS total_pnl,
    COUNT(*) AS trade_count
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY account_id, EXTRACT(HOUR FROM entry_time);
