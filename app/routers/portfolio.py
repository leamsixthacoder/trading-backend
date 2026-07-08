from datetime import date

from fastapi import APIRouter

from app.database import get_cursor
from app.schemas import (
    PortfolioBalanceOut,
    PortfolioPnlByDayOut,
    PortfolioPnlByMonthOut,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/balance", response_model=PortfolioBalanceOut)
def get_portfolio_balance():
    with get_cursor() as cur:
        cur.execute(
            "SELECT account_type, account_count, total_capital_base, total_trade_pnl, "
            "total_allocations, total_balance FROM portfolio_balance_by_type ORDER BY account_type"
        )
        by_type = cur.fetchall()

    total = {
        "account_count": sum(row["account_count"] for row in by_type),
        "total_capital_base": sum(row["total_capital_base"] for row in by_type),
        "total_trade_pnl": sum(row["total_trade_pnl"] for row in by_type),
        "total_allocations": sum(row["total_allocations"] for row in by_type),
        "total_balance": sum(row["total_balance"] for row in by_type),
    }
    return {"total": total, "by_type": by_type}


@router.get("/pnl/daily", response_model=list[PortfolioPnlByDayOut])
def get_portfolio_pnl_daily(start: date | None = None, end: date | None = None):
    with get_cursor() as cur:
        query = "SELECT day, pnl_net, trade_count FROM portfolio_pnl_by_day"
        params: list = []
        conditions = []
        if start is not None:
            conditions.append("day >= %s")
            params.append(start)
        if end is not None:
            conditions.append("day <= %s")
            params.append(end)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY day"

        cur.execute(query, params)
        return cur.fetchall()


@router.get("/pnl/monthly", response_model=list[PortfolioPnlByMonthOut])
def get_portfolio_pnl_monthly(start: date | None = None, end: date | None = None):
    with get_cursor() as cur:
        query = "SELECT month, pnl_net, trade_count FROM portfolio_pnl_by_month"
        params: list = []
        conditions = []
        if start is not None:
            conditions.append("month >= %s")
            params.append(start)
        if end is not None:
            conditions.append("month <= %s")
            params.append(end)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY month"

        cur.execute(query, params)
        return cur.fetchall()
