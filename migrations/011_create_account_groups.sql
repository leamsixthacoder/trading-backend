-- Migration 011: account_groups — user-defined groupings of accounts for
-- combined balance/equity viewing (e.g. "Prop Accounts", "Live Trading").
-- Many-to-many: an account can belong to more than one group. Separate
-- from the personal_portfolio account type and the /portfolio/* dashboard
-- rollup, which are unrelated existing features.

CREATE TABLE account_groups (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE account_group_members (
    group_id    UUID NOT NULL REFERENCES account_groups(id) ON DELETE CASCADE,
    account_id  UUID NOT NULL REFERENCES accounts(id),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, account_id)
);

CREATE INDEX idx_account_group_members_account ON account_group_members (account_id);
