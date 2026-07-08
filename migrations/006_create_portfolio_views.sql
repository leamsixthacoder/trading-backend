-- Migration 006: Portfolio-wide rollup views
-- Cross-account aggregates, built the same way as account_balances: derived
-- from trades + allocations, never a stored total. Grand total is summed
-- from portfolio_balance_by_type at the API layer rather than a separate
-- view, since it's a trivial reduction over a handful of rows.

CREATE VIEW portfolio_balance_by_type AS
SELECT
    account_type,
    COUNT(*)                    AS account_count,
    SUM(capital_base)           AS total_capital_base,
    SUM(total_trade_pnl)        AS total_trade_pnl,
    SUM(total_allocations)      AS total_allocations,
    SUM(current_balance)        AS total_balance
FROM account_balances
GROUP BY account_type;

COMMENT ON VIEW portfolio_balance_by_type IS
    'Cross-account balance rollup grouped by account_type. Grand total is summed from this at the API layer.';

CREATE VIEW portfolio_pnl_by_day AS
SELECT
    date_trunc('day', exit_time) AS day,
    SUM(pnl_net)                 AS pnl_net,
    COUNT(*)                     AS trade_count
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY date_trunc('day', exit_time);

CREATE VIEW portfolio_pnl_by_month AS
SELECT
    date_trunc('month', exit_time) AS month,
    SUM(pnl_net)                   AS pnl_net,
    COUNT(*)                       AS trade_count
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY date_trunc('month', exit_time);
