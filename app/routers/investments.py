from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from psycopg2.extras import Json

from app.database import get_cursor
from app.schemas import (
    HoldingCreate,
    HoldingOut,
    HoldingUpdate,
    PortfolioReturnOut,
    PortfolioSnapshotCreate,
    PortfolioSnapshotOut,
)

router = APIRouter(tags=["investments"])

PERIOD_DAYS = {
    "quarter": 90,
    "year": 365,
    "4y": 4 * 365,
    "5y": 5 * 365,
}


def _require_personal_portfolio_account(cur, account_id: UUID) -> None:
    cur.execute("SELECT account_type FROM accounts WHERE id = %s", (str(account_id),))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if row["account_type"] != "personal_portfolio":
        raise HTTPException(
            status_code=400,
            detail="Holdings can only be attached to a personal_portfolio account",
        )


@router.post("/holdings", response_model=HoldingOut, status_code=201)
def create_holding(body: HoldingCreate):
    with get_cursor() as cur:
        _require_personal_portfolio_account(cur, body.account_id)

        cur.execute(
            "INSERT INTO holdings (account_id, symbol, quantity, cost_basis, acquired_date, asset_class) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "RETURNING id, account_id, symbol, quantity, cost_basis, acquired_date, asset_class, created_at",
            (str(body.account_id), body.symbol, body.quantity, body.cost_basis, body.acquired_date, body.asset_class),
        )
        return cur.fetchone()


@router.get("/holdings", response_model=list[HoldingOut])
def list_holdings(account_id: UUID | None = None):
    query = (
        "SELECT id, account_id, symbol, quantity, cost_basis, acquired_date, asset_class, created_at "
        "FROM holdings"
    )
    params: list = []
    if account_id is not None:
        query += " WHERE account_id = %s"
        params.append(str(account_id))
    query += " ORDER BY acquired_date"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.patch("/holdings/{holding_id}", response_model=HoldingOut)
def update_holding(holding_id: UUID, body: HoldingUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{key} = %s" for key in fields)
    params = list(fields.values()) + [str(holding_id)]

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE holdings SET {set_clause} WHERE id = %s "
            "RETURNING id, account_id, symbol, quantity, cost_basis, acquired_date, asset_class, created_at",
            params,
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Holding not found")
        return row


@router.post("/portfolio-snapshots", response_model=PortfolioSnapshotOut, status_code=201)
def create_portfolio_snapshot(body: PortfolioSnapshotCreate):
    with get_cursor() as cur:
        _require_personal_portfolio_account(cur, body.account_id)

        cur.execute(
            "INSERT INTO portfolio_snapshots (account_id, snapshot_date, total_value, holdings_detail) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, account_id, snapshot_date, total_value, holdings_detail, created_at",
            (str(body.account_id), body.snapshot_date, body.total_value, Json(body.holdings_detail)),
        )
        return cur.fetchone()


@router.get("/portfolio-snapshots", response_model=list[PortfolioSnapshotOut])
def list_portfolio_snapshots(account_id: UUID | None = None, from_: date | None = None, to: date | None = None):
    query = (
        "SELECT id, account_id, snapshot_date, total_value, holdings_detail, created_at "
        "FROM portfolio_snapshots"
    )
    params: list = []
    conditions = []
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if from_ is not None:
        conditions.append("snapshot_date >= %s")
        params.append(from_)
    if to is not None:
        conditions.append("snapshot_date <= %s")
        params.append(to)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY snapshot_date"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/portfolio/returns", response_model=PortfolioReturnOut)
def get_portfolio_returns(account_id: UUID, period: str):
    if period not in PERIOD_DAYS:
        raise HTTPException(status_code=400, detail=f"period must be one of {list(PERIOD_DAYS)}")

    with get_cursor() as cur:
        cur.execute(
            "SELECT snapshot_date, total_value FROM portfolio_snapshots "
            "WHERE account_id = %s ORDER BY snapshot_date DESC LIMIT 1",
            (str(account_id),),
        )
        end_row = cur.fetchone()
        if end_row is None:
            raise HTTPException(status_code=404, detail="No snapshots exist for this account yet")

        cutoff = end_row["snapshot_date"] - timedelta(days=PERIOD_DAYS[period])
        cur.execute(
            "SELECT snapshot_date, total_value FROM portfolio_snapshots "
            "WHERE account_id = %s AND snapshot_date <= %s "
            "ORDER BY snapshot_date DESC LIMIT 1",
            (str(account_id), cutoff),
        )
        start_row = cur.fetchone()
        if start_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Not enough snapshot history for a '{period}' return yet "
                       f"(need a snapshot on or before {cutoff})",
            )

    start_value = start_row["total_value"]
    end_value = end_row["total_value"]
    return_pct = float((end_value - start_value) / start_value) if start_value else 0.0

    return {
        "account_id": account_id,
        "period": period,
        "start_date": start_row["snapshot_date"],
        "end_date": end_row["snapshot_date"],
        "start_value": start_value,
        "end_value": end_value,
        "return_pct": return_pct,
    }
