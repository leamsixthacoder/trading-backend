from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AccountOut(BaseModel):
    id: UUID
    label: str
    account_type: str
    provider: str | None
    capital_base: Decimal
    status: str
    created_at: datetime
    closed_at: datetime | None


class AccountBalanceOut(BaseModel):
    account_id: UUID
    label: str
    account_type: str
    status: str
    capital_base: Decimal
    total_trade_pnl: Decimal
    total_allocations: Decimal
    current_balance: Decimal


class AccountStatusHistoryOut(BaseModel):
    old_status: str | None
    new_status: str
    changed_at: datetime
    memo: str | None


class PnlByDayOut(BaseModel):
    account_id: UUID
    day: datetime
    pnl_net: Decimal
    trade_count: int


class PnlByMonthOut(BaseModel):
    account_id: UUID
    month: datetime
    pnl_net: Decimal
    trade_count: int


AllocationType = Literal["profit_share", "payout", "reserve", "reinvestment", "correction"]


class AllocationOut(BaseModel):
    id: UUID
    account_id: UUID
    type: AllocationType
    amount: Decimal
    period_start: date | None
    period_end: date | None
    computed_from: dict
    memo: str | None
    created_at: datetime
    created_by: str


class AllocationCreate(BaseModel):
    type: AllocationType
    amount: Decimal
    period_start: date | None = None
    period_end: date | None = None
    computed_from: dict = {}
    memo: str | None = None
    created_by: str = "manual"
