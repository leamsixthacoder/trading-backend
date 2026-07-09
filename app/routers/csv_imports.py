import json
import uuid
from uuid import UUID

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.csv_import_logic import PLATFORM_MAPS, parse_csv
from app.database import get_connection, get_cursor
from app.schemas import CsvImportOut, CsvImportPreviewOut, CsvImportPreviewRow, CsvImportRowError

router = APIRouter(prefix="/csv-imports", tags=["csv-imports"])

IMPORT_COLUMNS = (
    "id, account_id, source_platform, filename, imported_at, row_count, "
    "rows_inserted, rows_skipped_dupe, status, validation_errors"
)


def _require_account_exists(cur, account_id: UUID) -> None:
    cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(account_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Account not found")


def _require_known_platform(platform: str) -> None:
    if platform not in PLATFORM_MAPS:
        raise HTTPException(status_code=400, detail=f"platform must be one of {list(PLATFORM_MAPS)}")


def _read_csv_text(file: UploadFile) -> str:
    try:
        return file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Could not decode file as UTF-8 CSV")


@router.post("/preview", response_model=CsvImportPreviewOut)
def preview_csv_import(
    account_id: UUID = Form(...),
    platform: str = Form(...),
    file: UploadFile = File(...),
):
    _require_known_platform(platform)

    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        text = _read_csv_text(file)
        valid_trades, errors = parse_csv(text, platform)

        existing: set[str] = set()
        ids = [t.external_trade_id for t in valid_trades]
        if ids:
            cur.execute(
                "SELECT external_trade_id FROM trades WHERE account_id = %s AND external_trade_id = ANY(%s)",
                (str(account_id), ids),
            )
            existing = {r["external_trade_id"] for r in cur.fetchall()}

    seen: set[str] = set()
    rows: list[CsvImportPreviewRow] = []
    duplicate_count = 0
    for t in valid_trades:
        is_dupe = t.external_trade_id in existing or t.external_trade_id in seen
        seen.add(t.external_trade_id)
        if is_dupe:
            duplicate_count += 1
        rows.append(
            CsvImportPreviewRow(
                row_number=t.row_number,
                external_trade_id=t.external_trade_id,
                symbol=t.symbol,
                direction=t.direction,
                size=t.size,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                entry_time=t.entry_time,
                exit_time=t.exit_time,
                fees=t.fees,
                pnl_gross=t.pnl_gross,
                is_duplicate=is_dupe,
            )
        )

    error_row_numbers = {e.row_number for e in errors}
    return CsvImportPreviewOut(
        platform=platform,
        total_rows=len(valid_trades) + len(error_row_numbers),
        valid_count=len(valid_trades) - duplicate_count,
        duplicate_count=duplicate_count,
        error_count=len(error_row_numbers),
        rows=rows,
        errors=[CsvImportRowError(row_number=e.row_number, field=e.field, message=e.message) for e in errors],
    )


@router.post("", response_model=CsvImportOut, status_code=201)
def commit_csv_import(
    account_id: UUID = Form(...),
    platform: str = Form(...),
    file: UploadFile = File(...),
):
    _require_known_platform(platform)

    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

    text = _read_csv_text(file)
    valid_trades, errors = parse_csv(text, platform)
    error_row_numbers = {e.row_number for e in errors}
    total_rows = len(valid_trades) + len(error_row_numbers)
    status = "validated" if not errors else ("partial" if valid_trades else "failed")

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            import_batch_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO csv_imports (id, account_id, source_platform, filename, row_count, status, validation_errors) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    import_batch_id,
                    str(account_id),
                    platform,
                    file.filename or "upload.csv",
                    total_rows,
                    status,
                    json.dumps([{"row_number": e.row_number, "field": e.field, "message": e.message} for e in errors]),
                ),
            )

            inserted = 0
            skipped_dupe = 0
            for trade in valid_trades:
                cur.execute("SAVEPOINT trade_insert")
                try:
                    cur.execute(
                        "INSERT INTO trades ("
                        "account_id, import_batch_id, source_platform, external_trade_id, "
                        "symbol, direction, size, entry_price, exit_price, entry_time, exit_time, fees, pnl_gross"
                        ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            str(account_id), import_batch_id, platform, trade.external_trade_id,
                            trade.symbol, trade.direction, trade.size, trade.entry_price, trade.exit_price,
                            trade.entry_time, trade.exit_time, trade.fees, trade.pnl_gross,
                        ),
                    )
                    cur.execute("RELEASE SAVEPOINT trade_insert")
                    inserted += 1
                except psycopg2.errors.UniqueViolation:
                    cur.execute("ROLLBACK TO SAVEPOINT trade_insert")
                    skipped_dupe += 1

            cur.execute(
                f"UPDATE csv_imports SET rows_inserted = %s, rows_skipped_dupe = %s WHERE id = %s "
                f"RETURNING {IMPORT_COLUMNS}",
                (inserted, skipped_dupe, import_batch_id),
            )
            return cur.fetchone()


@router.get("", response_model=list[CsvImportOut])
def list_csv_imports(account_id: UUID | None = None):
    query = f"SELECT {IMPORT_COLUMNS} FROM csv_imports"
    params: list = []
    if account_id is not None:
        query += " WHERE account_id = %s"
        params.append(str(account_id))
    query += " ORDER BY imported_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
