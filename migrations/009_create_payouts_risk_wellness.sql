-- Migration 009: Phase 4 — payout eligibility calculator, multi-account
-- risk aggregation, wellness/decision support. Three independent tracks,
-- no changes to existing schema.

-- ============================================================
-- Track A: Payout Eligibility Calculation (NOT payout automation)
-- ============================================================

-- Firm-specific payout rules — differ by account_type (Lucid Flex vs
-- Topstep have different splits/schedules), so stored per account_type,
-- not hardcoded in application logic. Populated by the user via the API,
-- not seeded — no split percentages are guessed here.
CREATE TABLE payout_rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_type        account_type NOT NULL,
    profit_split_pct    NUMERIC(5,4) NOT NULL,
    min_payout_amount   NUMERIC(14,2),
    payout_frequency    TEXT,
    notes               TEXT,
    effective_date      DATE NOT NULL DEFAULT CURRENT_DATE
);

-- One row per computed eligibility check, not per actual payout. The
-- actual payout, once submitted and received (manual, on the firm's own
-- dashboard), gets recorded as an allocations row (type='payout') — this
-- table is upstream of that, just the "should I request one" calculation.
CREATE TABLE payout_eligibility_checks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL REFERENCES accounts(id),
    checked_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    eligible            BOOLEAN NOT NULL,
    computed_amount     NUMERIC(14,2),
    computed_from       JSONB NOT NULL,
    reason_if_ineligible TEXT
);

-- ============================================================
-- Track B: Multi-Account Risk Aggregation
-- ============================================================

-- Portfolio-level (not per-account) risk rules, extending Phase 2's
-- per-account risk_rules.
CREATE TABLE aggregate_risk_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_type       TEXT NOT NULL,   -- 'total_open_risk', 'total_daily_loss_all_accounts'
    scope           TEXT NOT NULL,   -- 'all', 'funded_only', 'personal_only'
    threshold       NUMERIC(14,2) NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT true
);

-- ============================================================
-- Track C: Wellness & Decision Support
-- ============================================================

CREATE TABLE emotional_state_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    account_id      UUID REFERENCES accounts(id),   -- nullable, some entries are general
    state_tags      TEXT[] DEFAULT '{}',
    intensity       INTEGER CHECK (intensity BETWEEN 1 AND 10),
    note            TEXT
);

CREATE TABLE trade_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id        UUID REFERENCES trades(id),
    what_happened   TEXT,
    what_went_well  TEXT,
    what_to_change  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
