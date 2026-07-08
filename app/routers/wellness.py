from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import get_cursor
from app.schemas import EmotionalStateLogCreate, EmotionalStateLogOut, TradeReviewCreate, TradeReviewOut

router = APIRouter(tags=["wellness"])


@router.post("/emotional-state-logs", response_model=EmotionalStateLogOut, status_code=201)
def create_emotional_state_log(body: EmotionalStateLogCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO emotional_state_logs (account_id, state_tags, intensity, note) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, logged_at, account_id, state_tags, intensity, note",
            (
                str(body.account_id) if body.account_id else None,
                body.state_tags,
                body.intensity,
                body.note,
            ),
        )
        return cur.fetchone()


@router.get("/emotional-state-logs", response_model=list[EmotionalStateLogOut])
def list_emotional_state_logs(
    account_id: UUID | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
):
    query = "SELECT id, logged_at, account_id, state_tags, intensity, note FROM emotional_state_logs"
    params: list = []
    conditions = []
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if from_ is not None:
        conditions.append("logged_at::date >= %s")
        params.append(from_)
    if to is not None:
        conditions.append("logged_at::date <= %s")
        params.append(to)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY logged_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.post("/trade-reviews", response_model=TradeReviewOut, status_code=201)
def create_trade_review(body: TradeReviewCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO trade_reviews (trade_id, what_happened, what_went_well, what_to_change) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, trade_id, what_happened, what_went_well, what_to_change, created_at",
            (
                str(body.trade_id) if body.trade_id else None,
                body.what_happened,
                body.what_went_well,
                body.what_to_change,
            ),
        )
        return cur.fetchone()


@router.get("/trade-reviews", response_model=list[TradeReviewOut])
def list_trade_reviews(trade_id: UUID | None = None):
    query = (
        "SELECT id, trade_id, what_happened, what_went_well, what_to_change, created_at "
        "FROM trade_reviews"
    )
    params: list = []
    if trade_id is not None:
        query += " WHERE trade_id = %s"
        params.append(str(trade_id))
    query += " ORDER BY created_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
