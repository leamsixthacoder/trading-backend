-- Migration 004: Derived views
-- No account balance is ever stored. It is always computed from trades
-- and allocations. This means the balance can never drift from its
-- source data — reconstructing history is just re-running the query.

CREATE VIEW account_balances AS
SELECT
    a.id                                AS account_id,
    a.label,
    a.account_type,
    a.status,
    a.capital_base,
    COALESCE(t.total_trade_pnl, 0)      AS total_trade_pnl,
    COALESCE(al.total_allocations, 0)   AS total_allocations,
    a.capital_base
        + COALESCE(t.total_trade_pnl, 0)
        + COALESCE(al.total_allocations, 0) AS current_balance
FROM accounts a
LEFT JOIN (
    SELECT account_id, SUM(pnl_net) AS total_trade_pnl
    FROM trades
    WHERE exit_time IS NOT NULL   -- only closed trades count toward realized P&L
    GROUP BY account_id
) t ON t.account_id = a.id
LEFT JOIN (
    SELECT account_id, SUM(amount) AS total_allocations
    FROM allocations
    GROUP BY account_id
) al ON al.account_id = a.id;

COMMENT ON VIEW account_balances IS
    'The only place "balance" should ever be read from. Never add a stored balance column to accounts.';

CREATE VIEW account_pnl_by_day AS
SELECT
    account_id,
    date_trunc('day', exit_time) AS day,
    SUM(pnl_net) AS pnl_net,
    COUNT(*) AS trade_count
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY account_id, date_trunc('day', exit_time);

CREATE VIEW account_pnl_by_month AS
SELECT
    account_id,
    date_trunc('month', exit_time) AS month,
    SUM(pnl_net) AS pnl_net,
    COUNT(*) AS trade_count
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY account_id, date_trunc('month', exit_time);
