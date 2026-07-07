#!/usr/bin/env python3
"""
CSV import pipeline: raw broker export -> validated trades table.

Design principles this script enforces:
  1. Every row is tied to exactly one account_id (passed explicitly,
     never inferred from the CSV) — this is the anti-leak guarantee.
  2. Dedup relies on the DB's UNIQUE(account_id, external_trade_id)
     constraint, not on script logic — the database is the source of
     truth for "have I seen this trade before."
  3. Nothing is written until every row in the batch has been validated
     structurally. Partial imports are recorded, not silently dropped.
  4. Platform-specific column mapping lives in one place (PLATFORM_MAPS)
     so adding a new broker format doesn't touch ingestion logic.

IMPORTANT — platform vs. account are independent:
    "platform" here means the CSV FORMAT (which execution software produced
    the export), not which fund/account the trades belong to. Lucid Flex and
    Topstep accounts don't have their own CSV format — you trade them through
    an execution platform (NinjaTrader, Tradovate, or TopstepX's native export),
    and THAT determines which --platform value to use. --account-id is what
    ties the imported trades to the correct Lucid/Topstep/personal account.
    Example: importing Topstep trades executed via NinjaTrader:
        --account-id <topstep-account-uuid> --platform ninjatrader --file export.csv

Usage:
    python import_csv.py --account-id <uuid> --platform ninjatrader --file trades.csv
"""

import argparse
import csv
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# Platform-specific column mapping.
# Add a new broker by adding one entry here — nothing else should need to
# change. Keys are the canonical field names; values are the column names
# as they appear in that platform's CSV export.
# ---------------------------------------------------------------------------
# NOTE ON ACCURACY: broker/platform CSV column names vary by version, account
# settings, and what the user selects at export time. The mappings below are
# best-available placeholders based on documented export formats — treat them
# as a starting point, not ground truth. Before trusting any platform's import
# in production, export one real file, compare its actual header row to the
# mapping below, and adjust. This is expected to need a one-time correction
# per platform on first real use, not a sign something is broken.
PLATFORM_MAPS = {
    # TradeStation — used for stock/personal live trading.
    # TradeStation's trade-list export column names depend on which report
    # (Order List vs. Position/Trade report) and columns the user has enabled.
    "tradestation": {
        "external_trade_id": "Order ID",
        "symbol": "Symbol",
        "direction": "Type",             # expected values like 'Buy'/'Sell'/'Short'/'Cover'
        "size": "Qty",
        "entry_price": "Entry Price",
        "exit_price": "Exit Price",
        "entry_time": "Entry Time",
        "exit_time": "Exit Time",
        "fees": "Commission",
        "pnl_gross": "P/L",
        "direction_map": {"Buy": "long", "Short": "short", "Sell": "long", "Cover": "short"},
        "time_format": "%m/%d/%Y %H:%M:%S",
    },
    # NinjaTrader — used for stock/personal live trading, and for Lucid/Topstep
    # accounts traded through NinjaTrader as the execution platform.
    # Export path: Trade Performance grid -> Executions -> right-click -> Export.
    # NinjaTrader exports at the EXECUTION level (fills), not paired round-trip
    # trades — a single round-trip trade may be two rows (entry fill + exit
    # fill) that need pairing. The mapping below assumes a round-trip/trade
    # export view rather than raw executions; verify which view was exported.
    "ninjatrader": {
        "external_trade_id": "Trade #",
        "symbol": "Instrument",
        "direction": "Market pos.",       # expected values: 'Long'/'Short'
        "size": "Qty",
        "entry_price": "Entry price",
        "exit_price": "Exit price",
        "entry_time": "Entry time",
        "exit_time": "Exit time",
        "fees": "Commission",
        "pnl_gross": "Profit",
        "direction_map": {"Long": "long", "Short": "short"},
        "time_format": "%m/%d/%Y %H:%M:%S",
    },
    # TopstepX native export — Topstep's own platform, "Trades" tab -> Export.
    # Available at both Trading Combine (eval) and Funded stages per Topstep's
    # own docs, so this is usable regardless of which stage an account is in.
    # Use this only if trading Topstep via TopstepX directly rather than
    # through NinjaTrader/Tradovate as the execution platform.
    "topstepx": {
        "external_trade_id": "Id",
        "symbol": "Contract",
        "direction": "Side",              # expected values: 'Buy'/'Sell' or 'Long'/'Short'
        "size": "Size",
        "entry_price": "Entry Price",
        "exit_price": "Exit Price",
        "entry_time": "Entered At",
        "exit_time": "Exited At",
        "fees": "Fees",
        "pnl_gross": "PnL",
        "direction_map": {"Buy": "long", "Sell": "short", "Long": "long", "Short": "short"},
        "time_format": "%m/%d/%Y %H:%M:%S",
    },
}


@dataclass
class ValidationError:
    row_number: int
    field: str
    message: str
    raw_row: dict = field(default_factory=dict)


@dataclass
class ValidatedTrade:
    external_trade_id: str
    symbol: str
    direction: str
    size: Decimal
    entry_price: Decimal
    exit_price: Decimal | None
    entry_time: datetime
    exit_time: datetime | None
    fees: Decimal
    pnl_gross: Decimal | None


def parse_decimal(raw: str, field_name: str, row_num: int, errors: list) -> Decimal | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        # strip common CSV artifacts: $, commas, parens-for-negative
        cleaned = raw.strip().replace("$", "").replace(",", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return Decimal(cleaned)
    except InvalidOperation:
        errors.append(ValidationError(row_num, field_name, f"Could not parse '{raw}' as a number"))
        return None


def parse_timestamp(raw: str, fmt: str, field_name: str, row_num: int, errors: list) -> datetime | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return datetime.strptime(raw.strip(), fmt)
    except ValueError:
        errors.append(ValidationError(row_num, field_name, f"Could not parse '{raw}' as timestamp with format {fmt}"))
        return None


def validate_row(row: dict, row_num: int, mapping: dict, errors: list) -> ValidatedTrade | None:
    """Validate a single CSV row. Returns None (and appends to errors) if invalid."""
    row_errors_before = len(errors)

    external_id = row.get(mapping["external_trade_id"], "").strip()
    if not external_id:
        errors.append(ValidationError(row_num, "external_trade_id", "Missing broker trade id — cannot dedupe safely, skipping row"))

    symbol = row.get(mapping["symbol"], "").strip()
    if not symbol:
        errors.append(ValidationError(row_num, "symbol", "Missing symbol"))

    raw_direction = row.get(mapping["direction"], "").strip()
    direction = mapping["direction_map"].get(raw_direction)
    if direction is None:
        errors.append(ValidationError(row_num, "direction", f"Unrecognized direction value '{raw_direction}'"))

    size = parse_decimal(row.get(mapping["size"]), "size", row_num, errors)
    if size is not None and size <= 0:
        errors.append(ValidationError(row_num, "size", f"Size must be positive, got {size}"))

    entry_price = parse_decimal(row.get(mapping["entry_price"]), "entry_price", row_num, errors)
    exit_price = parse_decimal(row.get(mapping["exit_price"]), "exit_price", row_num, errors)
    fees = parse_decimal(row.get(mapping["fees"]), "fees", row_num, errors) or Decimal("0")
    pnl_gross = parse_decimal(row.get(mapping["pnl_gross"]), "pnl_gross", row_num, errors)

    entry_time = parse_timestamp(row.get(mapping["entry_time"]), mapping["time_format"], "entry_time", row_num, errors)
    exit_time = parse_timestamp(row.get(mapping["exit_time"]), mapping["time_format"], "exit_time", row_num, errors)

    if entry_time is None:
        errors.append(ValidationError(row_num, "entry_time", "Missing/unparseable entry time — required field"))

    if entry_time and exit_time and exit_time < entry_time:
        errors.append(ValidationError(row_num, "exit_time", "Exit time is before entry time"))

    if len(errors) > row_errors_before:
        return None  # this row had at least one new error, reject the whole row

    return ValidatedTrade(
        external_trade_id=external_id,
        symbol=symbol,
        direction=direction,
        size=size,
        entry_price=entry_price,
        exit_price=exit_price,
        entry_time=entry_time,
        exit_time=exit_time,
        fees=fees,
        pnl_gross=pnl_gross,
    )


def run_import(conn, account_id: str, platform: str, filepath: str):
    if platform not in PLATFORM_MAPS:
        print(f"Unknown platform '{platform}'. Known platforms: {list(PLATFORM_MAPS.keys())}")
        sys.exit(1)

    mapping = PLATFORM_MAPS[platform]
    errors: list[ValidationError] = []
    valid_trades: list[ValidatedTrade] = []

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # row 1 is header
            trade = validate_row(row, row_num, mapping, errors)
            if trade:
                valid_trades.append(trade)

    total_rows = len(valid_trades) + len({e.row_number for e in errors})
    status = "validated" if not errors else ("partial" if valid_trades else "failed")

    cur = conn.cursor()

    # Record the import batch first, regardless of outcome — this is part
    # of the audit trail even for failed imports.
    import_batch_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO csv_imports
            (id, account_id, source_platform, filename, row_count, status, validation_errors)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            import_batch_id,
            account_id,
            platform,
            filepath,
            total_rows,
            status,
            json.dumps([vars(e) for e in errors]),
        ),
    )

    inserted = 0
    skipped_dupe = 0

    # Each trade insert gets its own savepoint so a duplicate (expected,
    # not an error) doesn't roll back the whole batch or the csv_imports
    # row we already wrote.
    for trade in valid_trades:
        cur.execute("SAVEPOINT trade_insert")
        try:
            cur.execute(
                """
                INSERT INTO trades (
                    account_id, import_batch_id, source_platform, external_trade_id,
                    symbol, direction, size, entry_price, exit_price,
                    entry_time, exit_time, fees, pnl_gross
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    account_id, import_batch_id, platform, trade.external_trade_id,
                    trade.symbol, trade.direction, trade.size, trade.entry_price, trade.exit_price,
                    trade.entry_time, trade.exit_time, trade.fees, trade.pnl_gross,
                ),
            )
            cur.execute("RELEASE SAVEPOINT trade_insert")
            inserted += 1
        except psycopg2.errors.UniqueViolation:
            # Same account + same broker trade id already exists.
            # This is the expected, safe outcome of re-importing a file —
            # not an error condition.
            cur.execute("ROLLBACK TO SAVEPOINT trade_insert")
            skipped_dupe += 1

    cur.execute(
        """
        UPDATE csv_imports
        SET rows_inserted = %s, rows_skipped_dupe = %s
        WHERE id = %s
        """,
        (inserted, skipped_dupe, import_batch_id),
    )

    conn.commit()

    print(f"Import batch {import_batch_id}")
    print(f"  Total rows read:     {total_rows}")
    print(f"  Inserted:            {inserted}")
    print(f"  Skipped (duplicate): {skipped_dupe}")
    print(f"  Validation errors:   {len(errors)}")
    if errors:
        print("  First few errors:")
        for e in errors[:5]:
            print(f"    row {e.row_number} [{e.field}]: {e.message}")


def main():
    parser = argparse.ArgumentParser(description="Import a broker CSV export into the trades table.")
    parser.add_argument("--account-id", required=True, help="UUID of the account this CSV belongs to")
    parser.add_argument("--platform", required=True, choices=PLATFORM_MAPS.keys())
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument("--dsn", default="dbname=trading_system", help="psycopg2 connection string")
    args = parser.parse_args()

    conn = psycopg2.connect(args.dsn)
    try:
        run_import(conn, args.account_id, args.platform, args.file)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
