from datetime import datetime
from decimal import Decimal
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
