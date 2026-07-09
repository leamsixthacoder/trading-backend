import csv
import io
from uuid import UUID

import psycopg2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from psycopg2.extras import Json

from app.csv_platforms import PLATFORM_MAPS, RowError, ValidatedTrade, validate_row
from app.database import get_cursor
from app.schemas import CsvImportOut, CsvImportPreviewOut, CsvImportPreviewRowOut, CsvImportRowErrorOut

router = APIRouter(prefix="/csv-imports", tags=["csv-imports"])

CSV_IMPORT_COLUMNS = (
    "id, account_id, source_platform, filename, imported_at, row_count, "
    "rows_inserted, rows_skipped_dupe, status, validation_errors"
)


def _require_account_exists(cur, account_id: UUID) -> None:
    cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(account_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Account not found")


def _require_platform(platform: str) -> dict:
    mapping = PLATFORM_MAPS.get(platform)
    if mapping is None:
        raise HTTPException(status_code=400, detail=f"Unknown platform '{platform}'. Known: {list(PLATFORM_MAPS)}")
    return mapping


async def _read_and_validate(file: UploadFile, mapping: dict) -> tuple[int, list[ValidatedTrade], list[RowError]]:
    raw = await file.read()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    rows = list(reader)

    errors: list[RowError] = []
    valid_trades: list[ValidatedTrade] = []
    for row_num, row in enumerate(rows, start=2):  # row 1 is the header
        trade = validate_row(row, row_num, mapping, errors)
        if trade:
            valid_trades.append(trade)

    return len(rows), valid_trades, errors


@router.post("/preview", response_model=CsvImportPreviewOut)
async def preview_csv_import(
    account_id: UUID = Form(...),
    platform: str = Form(...),
    file: UploadFile = File(...),
):
    mapping = _require_platform(platform)
    total_rows, valid_trades, errors = await _read_and_validate(file, mapping)

    external_ids = [t.external_trade_id for t in valid_trades]
    duplicates: set[str] = set()
    with get_cursor() as cur:
        _require_account_exists(cur, account_id)
        if external_ids:
            cur.execute(
                "SELECT external_trade_id FROM trades WHERE account_id = %s AND external_trade_id = ANY(%s)",
                (str(account_id), external_ids),
            )
            duplicates = {r["external_trade_id"] for r in cur.fetchall()}

    preview_rows = [
        CsvImportPreviewRowOut(
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
            is_duplicate=t.external_trade_id in duplicates,
        )
        for t in valid_trades
    ]

    return CsvImportPreviewOut(
        platform=platform,
        total_rows=total_rows,
        valid_count=len(valid_trades) - len(duplicates),
        duplicate_count=len(duplicates),
        error_count=len(errors),
        rows=preview_rows,
        errors=[CsvImportRowErrorOut(row_number=e.row_number, field=e.field, message=e.message) for e in errors],
    )


@router.post("", response_model=CsvImportOut, status_code=201)
async def commit_csv_import(
    account_id: UUID = Form(...),
    platform: str = Form(...),
    file: UploadFile = File(...),
):
    mapping = _require_platform(platform)
    total_rows, valid_trades, errors = await _read_and_validate(file, mapping)
    status = "validated" if not errors else ("partial" if valid_trades else "failed")

    with get_cursor() as cur:
        _require_account_exists(cur, account_id)

        cur.execute(
            "INSERT INTO csv_imports (account_id, source_platform, filename, row_count, status, validation_errors) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                str(account_id),
                platform,
                file.filename or "upload.csv",
                total_rows,
                status,
                Json([{"row_number": e.row_number, "field": e.field, "message": e.message} for e in errors]),
            ),
        )
        import_batch_id = cur.fetchone()["id"]

        inserted = 0
        skipped_dupe = 0
        for t in valid_trades:
            cur.execute("SAVEPOINT trade_insert")
            try:
                cur.execute(
                    "INSERT INTO trades (account_id, import_batch_id, source_platform, external_trade_id, "
                    "symbol, direction, size, entry_price, exit_price, entry_time, exit_time, fees, pnl_gross) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        str(account_id), str(import_batch_id), platform, t.external_trade_id,
                        t.symbol, t.direction, t.size, t.entry_price, t.exit_price,
                        t.entry_time, t.exit_time, t.fees, t.pnl_gross,
                    ),
                )
                cur.execute("RELEASE SAVEPOINT trade_insert")
                inserted += 1
            except psycopg2.errors.UniqueViolation:
                # Same account + broker trade id already exists — the expected,
                # safe outcome of re-importing a file, not an error.
                cur.execute("ROLLBACK TO SAVEPOINT trade_insert")
                skipped_dupe += 1

        cur.execute(
            f"UPDATE csv_imports SET rows_inserted = %s, rows_skipped_dupe = %s "
            f"WHERE id = %s RETURNING {CSV_IMPORT_COLUMNS}",
            (inserted, skipped_dupe, str(import_batch_id)),
        )
        return cur.fetchone()


@router.get("", response_model=list[CsvImportOut])
def list_csv_imports(account_id: UUID | None = None):
    query = f"SELECT {CSV_IMPORT_COLUMNS} FROM csv_imports"
    params: list = []
    if account_id is not None:
        query += " WHERE account_id = %s"
        params.append(str(account_id))
    query += " ORDER BY imported_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
