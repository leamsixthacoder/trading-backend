from datetime import date, timedelta
from uuid import UUID, uuid4

import psycopg2
from fastapi import APIRouter, HTTPException, Query

from app.database import get_cursor
from app.schemas import TradeCreate, TradeOut, TradeUpdate

router = APIRouter(prefix="/trades", tags=["trades"])

TRADE_COLUMNS = (
    "id, account_id, import_batch_id, source_platform, external_trade_id, "
    "symbol, direction, size, entry_price, exit_price, entry_time, exit_time, "
    "fees, pnl_gross, pnl_net, tags, notes, created_at"
)


def _require_account_exists(cur, account_id: UUID) -> None:
    cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(account_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Account not found")


@router.post("", response_model=TradeOut, status_code=201)
def create_trade(body: TradeCreate):
    # Manually-entered trades have no broker fill id — mint one so the
    # (account_id, external_trade_id) dedup constraint still holds.
    external_trade_id = body.external_trade_id or f"manual-{uuid4()}"

    with get_cursor() as cur:
        _require_account_exists(cur, body.account_id)

        try:
            cur.execute(
                "INSERT INTO trades ("
                "account_id, import_batch_id, source_platform, external_trade_id, "
                "symbol, direction, size, entry_price, exit_price, entry_time, exit_time, "
                "fees, pnl_gross, tags, notes"
                ") VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                f"RETURNING {TRADE_COLUMNS}",
                (
                    str(body.account_id),
                    "manual",
                    external_trade_id,
                    body.symbol,
                    body.direction,
                    body.size,
                    body.entry_price,
                    body.exit_price,
                    body.entry_time,
                    body.exit_time,
                    body.fees,
                    body.pnl_gross,
                    body.tags,
                    body.notes,
                ),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(
                status_code=409,
                detail="A trade with this external_trade_id already exists for this account",
            )
        return cur.fetchone()


@router.get("", response_model=list[TradeOut])
def list_trades(
    account_id: UUID | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    exit_date: date | None = None,
):
    query = f"SELECT {TRADE_COLUMNS} FROM trades"
    params: list = []
    conditions = []
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if symbol is not None:
        conditions.append("symbol = %s")
        params.append(symbol)
    if direction is not None:
        conditions.append("direction = %s")
        params.append(direction)
    if from_ is not None:
        conditions.append("entry_time >= %s")
        params.append(from_)
    if to is not None:
        # `to` is a calendar date; comparing entry_time (a timestamp)
        # against midnight of that date would exclude every trade from
        # that day except one at exactly 00:00. Use the exclusive start
        # of the next day instead so `to` means "through end of that day".
        conditions.append("entry_time < %s")
        params.append(to + timedelta(days=1))
    if exit_date is not None:
        # Same grouping as account_pnl_by_day/account_pnl_by_month (migration
        # 004): a trade counts toward the day it closed, not the day it
        # opened, and only closed trades have a realized P&L to show.
        conditions.append("date_trunc('day', exit_time) = %s")
        params.append(exit_date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY entry_time DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.patch("/{trade_id}", response_model=TradeOut)
def update_trade(trade_id: UUID, body: TradeUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{key} = %s" for key in fields)
    params = list(fields.values()) + [str(trade_id)]

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE trades SET {set_clause} WHERE id = %s RETURNING {TRADE_COLUMNS}",
            params,
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Trade not found")
        return row
