"""Platform column-mapping/validation for broker CSV trade exports, used by
the /csv-imports API route.

Deliberately NOT shared with scripts/import_csv.py: that script is documented
(README.md, BACKEND_SETUP.md) to run standalone as `python scripts/import_csv.py`
with no `app` package on its path, so importing from here would break it.
Keep PLATFORM_MAPS in sync by hand if a broker's export format changes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

PLATFORM_MAPS = {
    "tradestation": {
        "external_trade_id": "Order ID",
        "symbol": "Symbol",
        "direction": "Type",
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
    "ninjatrader": {
        "external_trade_id": "Trade #",
        "symbol": "Instrument",
        "direction": "Market pos.",
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
    "topstepx": {
        "external_trade_id": "Id",
        "symbol": "Contract",
        "direction": "Side",
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
class RowError:
    row_number: int
    field: str
    message: str


@dataclass
class ValidatedTrade:
    row_number: int
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


def _parse_decimal(raw: str | None, field_name: str, row_num: int, errors: list[RowError]) -> Decimal | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        cleaned = raw.strip().replace("$", "").replace(",", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return Decimal(cleaned)
    except InvalidOperation:
        errors.append(RowError(row_num, field_name, f"Could not parse '{raw}' as a number"))
        return None


def _parse_timestamp(raw: str | None, fmt: str, field_name: str, row_num: int, errors: list[RowError]) -> datetime | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return datetime.strptime(raw.strip(), fmt)
    except ValueError:
        errors.append(RowError(row_num, field_name, f"Could not parse '{raw}' as timestamp with format {fmt}"))
        return None


def validate_row(row: dict, row_num: int, mapping: dict, errors: list[RowError]) -> ValidatedTrade | None:
    row_errors_before = len(errors)

    external_id = (row.get(mapping["external_trade_id"]) or "").strip()
    if not external_id:
        errors.append(RowError(row_num, "external_trade_id", "Missing broker trade id — cannot dedupe safely, skipping row"))

    symbol = (row.get(mapping["symbol"]) or "").strip()
    if not symbol:
        errors.append(RowError(row_num, "symbol", "Missing symbol"))

    raw_direction = (row.get(mapping["direction"]) or "").strip()
    direction = mapping["direction_map"].get(raw_direction)
    if direction is None:
        errors.append(RowError(row_num, "direction", f"Unrecognized direction value '{raw_direction}'"))

    size = _parse_decimal(row.get(mapping["size"]), "size", row_num, errors)
    if size is not None and size <= 0:
        errors.append(RowError(row_num, "size", f"Size must be positive, got {size}"))

    entry_price = _parse_decimal(row.get(mapping["entry_price"]), "entry_price", row_num, errors)
    exit_price = _parse_decimal(row.get(mapping["exit_price"]), "exit_price", row_num, errors)
    fees = _parse_decimal(row.get(mapping["fees"]), "fees", row_num, errors) or Decimal("0")
    pnl_gross = _parse_decimal(row.get(mapping["pnl_gross"]), "pnl_gross", row_num, errors)

    entry_time = _parse_timestamp(row.get(mapping["entry_time"]), mapping["time_format"], "entry_time", row_num, errors)
    exit_time = _parse_timestamp(row.get(mapping["exit_time"]), mapping["time_format"], "exit_time", row_num, errors)

    if entry_time is None:
        errors.append(RowError(row_num, "entry_time", "Missing/unparseable entry time — required field"))

    if entry_time and exit_time and exit_time < entry_time:
        errors.append(RowError(row_num, "exit_time", "Exit time is before entry time"))

    if entry_price is None:
        errors.append(RowError(row_num, "entry_price", "Missing/unparseable entry price — required field"))

    if len(errors) > row_errors_before:
        return None

    return ValidatedTrade(
        row_number=row_num,
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
