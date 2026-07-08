-- Migration 005: Seed the accounts you actually have today.
-- Only rows for accounts that are actually purchased/funded go here. The
-- rest of the ~$550k plan (2 more Lucid Flex, 2 Topstep, personal live) is
-- an ongoing acquisition plan, not current state — add each one with an
-- INSERT once it's actually bought, rather than pre-seeding placeholders.

INSERT INTO accounts (label, account_type, provider, capital_base, status) VALUES
    ('Lucid Flex #1', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Lucid Flex #2', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Lucid Flex #3', 'funded_lucid',   'lucid_flex', 50000.00, 'active');

-- Add each additional account here once it's actually purchased/funded:
-- INSERT INTO accounts (label, account_type, provider, capital_base, status) VALUES
--     ('Lucid Flex #4', 'funded_lucid',   'lucid_flex', 50000.00, 'active');
-- INSERT INTO accounts (label, account_type, provider, capital_base, status) VALUES
--     ('Topstep #1', 'funded_topstep', 'topstep', 150000.00, 'active');
-- INSERT INTO accounts (label, account_type, provider, capital_base, status) VALUES
--     ('Personal Live', 'personal_live', NULL, <amount>, 'active');
