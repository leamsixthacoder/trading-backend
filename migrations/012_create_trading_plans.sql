-- Migration 012: trading_plans — a named plan (rules, checklist, attached
-- strategies) scoped to exactly one account or one account_group, plus a
-- daily log of whether each checklist item was followed.
--
-- Scope is exclusive (account XOR group), enforced by CHECK below, matching
-- how position_sizing_rules already uses a dual-nullable-FK for "strategy
-- level, account level, or both" — here a plan applies to one account or
-- one group, never a bare mix of the two.

CREATE TYPE trading_plan_status AS ENUM ('active', 'archived');

CREATE TABLE trading_plans (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    description       TEXT,
    account_id        UUID REFERENCES accounts(id),
    account_group_id  UUID REFERENCES account_groups(id),
    status            trading_plan_status NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_trading_plans_scope CHECK (
        (account_id IS NOT NULL AND account_group_id IS NULL) OR
        (account_id IS NULL AND account_group_id IS NOT NULL)
    )
);

CREATE INDEX idx_trading_plans_account ON trading_plans (account_id);
CREATE INDEX idx_trading_plans_group ON trading_plans (account_group_id);

-- Strategies attached to a plan (many-to-many — a plan can reference more
-- than one strategy, e.g. a "London session" plan running two setups).
CREATE TABLE trading_plan_strategies (
    plan_id      UUID NOT NULL REFERENCES trading_plans(id) ON DELETE CASCADE,
    strategy_id  UUID NOT NULL REFERENCES strategies(id),
    added_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (plan_id, strategy_id)
);

-- The plan's checklist ("checked economic calendar", "risk sized per plan",
-- etc). Plan-level, independent of which attached strategy is traded that
-- day.
CREATE TABLE trading_plan_checklist_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID NOT NULL REFERENCES trading_plans(id) ON DELETE CASCADE,
    label       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trading_plan_checklist_items_plan ON trading_plan_checklist_items (plan_id);

-- One row per plan per day the checklist was opened/logged.
CREATE TABLE trading_plan_daily_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID NOT NULL REFERENCES trading_plans(id) ON DELETE CASCADE,
    log_date    DATE NOT NULL,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_trading_plan_daily_logs_plan_date UNIQUE (plan_id, log_date)
);

CREATE INDEX idx_trading_plan_daily_logs_plan ON trading_plan_daily_logs (plan_id);

-- Per-checklist-item check state for a given day's log. Deleting a
-- checklist item drops its historical checks along with it (ON DELETE
-- CASCADE) — simplest option for a single-user journal, no orphaned rows.
CREATE TABLE trading_plan_daily_log_items (
    daily_log_id       UUID NOT NULL REFERENCES trading_plan_daily_logs(id) ON DELETE CASCADE,
    checklist_item_id  UUID NOT NULL REFERENCES trading_plan_checklist_items(id) ON DELETE CASCADE,
    checked            BOOLEAN NOT NULL DEFAULT false,
    checked_at         TIMESTAMPTZ,
    PRIMARY KEY (daily_log_id, checklist_item_id)
);
