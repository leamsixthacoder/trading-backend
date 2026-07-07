from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import (
    AccountBalanceOut,
    AccountOut,
    AccountStatusHistoryOut,
    PnlByDayOut,
    PnlByMonthOut,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _require_account_exists(cur, account_id: UUID) -> None:
    cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(account_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Account not found")


@router.get("", response_model=list[AccountOut])
def list_accounts():
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, label, account_type, provider, capital_base, status, created_at, closed_at "
            "FROM accounts ORDER BY label"
        )
        return cur.fetchall()


@router.get("/{account_id}/balance", response_model=AccountBalanceOut)
def get_account_balance(account_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "SELECT account_id, label, account_type, status, capital_base, "
            "total_trade_pnl, total_allocations, current_balance "
            "FROM account_balances WHERE account_id = %s",
            (str(account_id),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return row


@router.get("/{account_id}/status-history", response_model=list[AccountStatusHistoryOut])
def get_account_status_history(account_id: UUID):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        cur.execute(
            "SELECT old_status, new_status, changed_at, memo "
            "FROM account_status_history WHERE account_id = %s ORDER BY changed_at",
            (str(account_id),),
        )
        return cur.fetchall()


@router.get("/{account_id}/pnl/daily", response_model=list[PnlByDayOut])
def get_account_pnl_daily(account_id: UUID, start: date | None = None, end: date | None = None):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        query = "SELECT account_id, day, pnl_net, trade_count FROM account_pnl_by_day WHERE account_id = %s"
        params: list = [str(account_id)]
        if start is not None:
            query += " AND day >= %s"
            params.append(start)
        if end is not None:
            query += " AND day <= %s"
            params.append(end)
        query += " ORDER BY day"

        cur.execute(query, params)
        return cur.fetchall()


@router.get("/{account_id}/pnl/monthly", response_model=list[PnlByMonthOut])
def get_account_pnl_monthly(account_id: UUID, start: date | None = None, end: date | None = None):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        query = "SELECT account_id, month, pnl_net, trade_count FROM account_pnl_by_month WHERE account_id = %s"
        params: list = [str(account_id)]
        if start is not None:
            query += " AND month >= %s"
            params.append(start)
        if end is not None:
            query += " AND month <= %s"
            params.append(end)
        query += " ORDER BY month"

        cur.execute(query, params)
        return cur.fetchall()
