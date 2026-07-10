from datetime import date
from uuid import UUID

import psycopg2
from fastapi import APIRouter, HTTPException
from psycopg2.extras import Json

from app.database import get_cursor
from app.schemas import (
    AccountBalanceOut,
    AccountCreate,
    AccountOut,
    AccountRuleCreate,
    AccountRuleOut,
    AccountRuleUpdate,
    AccountStatusHistoryOut,
    AllocationCreate,
    AllocationOut,
    PnlByDayOut,
    PnlByMonthOut,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])

PROVIDER_BY_TYPE = {
    "funded_lucid": "lucid_flex",
    "funded_topstep": "topstep",
    "personal_live": None,
    "personal_portfolio": None,
}


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


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO accounts (label, account_type, provider, capital_base) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, label, account_type, provider, capital_base, status, created_at, closed_at",
            (body.label, body.account_type, PROVIDER_BY_TYPE[body.account_type], body.capital_base),
        )
        return cur.fetchone()


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


@router.get("/{account_id}/allocations", response_model=list[AllocationOut])
def list_account_allocations(account_id: UUID):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        cur.execute(
            "SELECT id, account_id, type, amount, period_start, period_end, "
            "computed_from, memo, created_at, created_by "
            "FROM allocations WHERE account_id = %s ORDER BY created_at",
            (str(account_id),),
        )
        return cur.fetchall()


@router.post("/{account_id}/allocations", response_model=AllocationOut, status_code=201)
def create_account_allocation(account_id: UUID, body: AllocationCreate):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        cur.execute(
            "INSERT INTO allocations (account_id, type, amount, period_start, period_end, "
            "computed_from, memo, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, account_id, type, amount, period_start, period_end, "
            "computed_from, memo, created_at, created_by",
            (
                str(account_id),
                body.type,
                body.amount,
                body.period_start,
                body.period_end,
                Json(body.computed_from),
                body.memo,
                body.created_by,
            ),
        )
        return cur.fetchone()


ACCOUNT_RULE_COLUMNS = "id, account_id, rule_type, threshold, created_at, updated_at"


@router.post("/{account_id}/rules", response_model=AccountRuleOut, status_code=201)
def create_account_rule(account_id: UUID, body: AccountRuleCreate):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)
        try:
            cur.execute(
                f"INSERT INTO account_rules (account_id, rule_type, threshold) "
                f"VALUES (%s, %s, %s) RETURNING {ACCOUNT_RULE_COLUMNS}",
                (str(account_id), body.rule_type, body.threshold),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(
                status_code=409,
                detail=f"A '{body.rule_type}' rule already exists for this account — use PATCH to update it",
            )
        return cur.fetchone()


@router.get("/{account_id}/rules", response_model=list[AccountRuleOut])
def list_account_rules(account_id: UUID):
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)
        cur.execute(
            f"SELECT {ACCOUNT_RULE_COLUMNS} FROM account_rules "
            f"WHERE account_id = %s ORDER BY rule_type",
            (str(account_id),),
        )
        return cur.fetchall()


@router.patch("/{account_id}/rules/{rule_id}", response_model=AccountRuleOut)
def update_account_rule(account_id: UUID, rule_id: UUID, body: AccountRuleUpdate):
    with get_cursor() as cur:
        cur.execute(
            f"UPDATE account_rules SET threshold = %s, updated_at = now() "
            f"WHERE id = %s AND account_id = %s RETURNING {ACCOUNT_RULE_COLUMNS}",
            (body.threshold, str(rule_id), str(account_id)),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Account rule not found")
        return row


@router.delete("/{account_id}/rules/{rule_id}", status_code=204)
def delete_account_rule(account_id: UUID, rule_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM account_rules WHERE id = %s AND account_id = %s",
            (str(rule_id), str(account_id)),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Account rule not found")
