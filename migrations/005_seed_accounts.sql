-- Migration 005: Seed the accounts you actually have today.
-- Adjust labels/capital_base to match reality before running.

INSERT INTO accounts (label, account_type, provider, capital_base, status) VALUES
    ('Lucid Flex #1', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Lucid Flex #2', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Lucid Flex #3', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Lucid Flex #4', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Lucid Flex #5', 'funded_lucid',   'lucid_flex', 50000.00, 'active'),
    ('Topstep #1',    'funded_topstep', 'topstep',    150000.00, 'active'),
    ('Topstep #2',    'funded_topstep', 'topstep',    150000.00, 'active');

-- Add personal live account(s) here once you confirm capital_base per account:
-- INSERT INTO accounts (label, account_type, provider, capital_base, status) VALUES
--     ('Personal Live', 'personal_live', NULL, <amount>, 'active');
