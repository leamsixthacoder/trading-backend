from fastapi import APIRouter

from app.database import get_cursor
from app.schemas import DashboardSummaryOut

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
