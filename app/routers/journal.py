from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import get_cursor
from app.schemas import JournalEntryCreate, JournalEntryOut

router = APIRouter(prefix="/journal-entries", tags=["journal"])


@router.get("", response_model=list[JournalEntryOut])
def list_journal_entries(
    account_id: UUID | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    type: str | None = None,
):
    query = "SELECT id, account_id, entry_date, entry_type, content, created_at FROM journal_entries"
    params: list = []
    conditions = []
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if from_ is not None:
        conditions.append("entry_date >= %s")
        params.append(from_)
    if to is not None:
        conditions.append("entry_date <= %s")
        params.append(to)
    if type is not None:
        conditions.append("entry_type = %s")
        params.append(type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY entry_date DESC, created_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.post("", response_model=JournalEntryOut, status_code=201)
def create_journal_entry(body: JournalEntryCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO journal_entries (account_id, entry_date, entry_type, content) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, account_id, entry_date, entry_type, content, created_at",
            (
                str(body.account_id) if body.account_id else None,
                body.entry_date,
                body.entry_type,
                body.content,
            ),
        )
        return cur.fetchone()
