from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import AccountBalanceOut, AccountOut, AccountStatusHistoryOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


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
        cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(account_id),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Account not found")

        cur.execute(
            "SELECT old_status, new_status, changed_at, memo "
            "FROM account_status_history WHERE account_id = %s ORDER BY changed_at",
            (str(account_id),),
        )
        return cur.fetchall()
