from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import PnlByDayOut, PnlByHourOut, PnlByMonthOut, PnlBySetupOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/pnl")
def get_pnl(account_id: UUID, period: str = "day", start: date | None = None, end: date | None = None):
    if period not in ("day", "month"):
        raise HTTPException(status_code=400, detail="period must be 'day' or 'month'")

    view = "account_pnl_by_day" if period == "day" else "account_pnl_by_month"
    column = "day" if period == "day" else "month"
    model = PnlByDayOut if period == "day" else PnlByMonthOut

    query = f"SELECT account_id, {column}, pnl_net, trade_count FROM {view} WHERE account_id = %s"
    params: list = [str(account_id)]
    if start is not None:
        query += f" AND {column} >= %s"
        params.append(start)
    if end is not None:
        query += f" AND {column} <= %s"
        params.append(end)
    query += f" ORDER BY {column}"

    with get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [model(**row) for row in rows]


@router.get("/pnl-by-setup", response_model=list[PnlBySetupOut])
def get_pnl_by_setup(account_id: UUID | None = None):
    query = (
        "SELECT account_id, setup_tag, total_pnl, trade_count, avg_pnl, win_rate "
        "FROM pnl_by_setup"
    )
    params: list = []
    if account_id is not None:
        query += " WHERE account_id = %s"
        params.append(str(account_id))
    query += " ORDER BY account_id, setup_tag"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/pnl-by-hour", response_model=list[PnlByHourOut])
def get_pnl_by_hour(account_id: UUID | None = None):
    query = "SELECT account_id, hour_of_day, total_pnl, trade_count FROM pnl_by_hour_of_day"
    params: list = []
    if account_id is not None:
        query += " WHERE account_id = %s"
        params.append(str(account_id))
    query += " ORDER BY account_id, hour_of_day"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
