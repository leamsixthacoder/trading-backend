from datetime import date

from fastapi import APIRouter

from app.database import get_cursor
from app.schemas import DashboardSummaryOut, RuleViolationsSummaryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary():
    with get_cursor() as cur:
        cur.execute(
            "SELECT b.account_id, b.label, b.account_type, b.status, b.current_balance, "
            "COALESCE(p.pnl_net, 0) AS today_pnl "
            "FROM account_balances b "
            "LEFT JOIN account_pnl_by_day p "
            "  ON p.account_id = b.account_id AND p.day = date_trunc('day', now()) "
            "ORDER BY b.label"
        )
        accounts = cur.fetchall()

    total_capital = sum(row["current_balance"] for row in accounts)
    total_pnl_today = sum(row["today_pnl"] for row in accounts)

    return {
        "accounts": accounts,
        "total_capital": total_capital,
        "total_pnl_today": total_pnl_today,
    }


@router.get("/rule-violations", response_model=RuleViolationsSummaryOut)
def get_rule_violations(start: date, end: date):
    with get_cursor() as cur:
        cur.execute(
            "SELECT ar.account_id, a.label AS account_label, ar.rule_type, ar.threshold "
            "FROM account_rules ar JOIN accounts a ON a.id = ar.account_id "
            "ORDER BY a.label, ar.rule_type"
        )
        rules = cur.fetchall()

        # cum_pnl/cum_low are the running trade-only equity curve since the
        # account's first trade (same simplification as the Account Equity
        # chart's cumulativeBalanceSeries — allocations aren't folded in).
        # They're computed over each account's full history, then filtered
        # to the requested range, so the running totals don't reset at
        # `start`.
        cur.execute(
            "WITH cum AS ("
            "  SELECT account_id, day, pnl_net,"
            "    SUM(pnl_net) OVER (PARTITION BY account_id ORDER BY day) AS cum_pnl"
            "  FROM account_pnl_by_day"
            "), running AS ("
            "  SELECT account_id, day, pnl_net, cum_pnl,"
            "    MIN(cum_pnl) OVER (PARTITION BY account_id ORDER BY day) AS cum_low"
            "  FROM cum"
            ") "
            "SELECT account_id, day, pnl_net, cum_pnl, cum_low FROM running "
            "WHERE day BETWEEN %s AND %s ORDER BY account_id, day",
            (start, end),
        )
        days_by_account: dict = {}
        for row in cur.fetchall():
            days_by_account.setdefault(row["account_id"], []).append(row)

    violations = []
    total_breached_days = 0
    for rule in rules:
        days = days_by_account.get(rule["account_id"], [])
        breached_days = 0
        currently_breached = False
        for day_row in days:
            if rule["rule_type"] == "daily_loss_limit":
                breached = day_row["pnl_net"] <= -rule["threshold"]
            elif rule["rule_type"] == "profit_target":
                breached = day_row["cum_pnl"] >= rule["threshold"]
            else:  # max_loss_limit
                breached = -day_row["cum_low"] >= rule["threshold"]
            if breached:
                breached_days += 1
            currently_breached = breached

        violations.append(
            {
                "account_id": rule["account_id"],
                "account_label": rule["account_label"],
                "rule_type": rule["rule_type"],
                "threshold": rule["threshold"],
                "breached_days": breached_days,
                "currently_breached": currently_breached,
            }
        )
        total_breached_days += breached_days

    return {
        "start": start,
        "end": end,
        "violations": violations,
        "total_breached_days": total_breached_days,
    }
