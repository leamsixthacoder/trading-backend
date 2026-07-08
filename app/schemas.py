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


class PortfolioBalanceByType(BaseModel):
    account_type: str
    account_count: int
    total_capital_base: Decimal
    total_trade_pnl: Decimal
    total_allocations: Decimal
    total_balance: Decimal


class PortfolioBalanceTotal(BaseModel):
    account_count: int
    total_capital_base: Decimal
    total_trade_pnl: Decimal
    total_allocations: Decimal
    total_balance: Decimal


class PortfolioBalanceOut(BaseModel):
    total: PortfolioBalanceTotal
    by_type: list[PortfolioBalanceByType]


class PortfolioPnlByDayOut(BaseModel):
    day: datetime
    pnl_net: Decimal
    trade_count: int


class PortfolioPnlByMonthOut(BaseModel):
    month: datetime
    pnl_net: Decimal
    trade_count: int


JournalEntryType = Literal["daily_log", "meeting_note", "general"]


class JournalEntryOut(BaseModel):
    id: UUID
    account_id: UUID | None
    entry_date: date
    entry_type: JournalEntryType
    content: str
    created_at: datetime


class JournalEntryCreate(BaseModel):
    account_id: UUID | None = None
    entry_date: date
    entry_type: JournalEntryType
    content: str


class RiskRuleOut(BaseModel):
    id: UUID
    account_id: UUID | None
    rule_type: str
    threshold: Decimal
    active: bool
    created_at: datetime


class RiskRuleCreate(BaseModel):
    account_id: UUID | None = None
    rule_type: str
    threshold: Decimal
    active: bool = True


class RiskAlertOut(BaseModel):
    id: UUID
    account_id: UUID
    risk_rule_id: UUID
    triggered_at: datetime
    actual_value: Decimal
    threshold_value: Decimal
    acknowledged: bool


class PnlBySetupOut(BaseModel):
    account_id: UUID
    setup_tag: str
    total_pnl: Decimal
    trade_count: int
    avg_pnl: Decimal | None
    win_rate: float | None


class PnlByHourOut(BaseModel):
    account_id: UUID
    hour_of_day: int
    total_pnl: Decimal
    trade_count: int


class DashboardAccountRow(BaseModel):
    account_id: UUID
    label: str
    account_type: str
    status: str
    current_balance: Decimal
    today_pnl: Decimal


class DashboardSummaryOut(BaseModel):
    accounts: list[DashboardAccountRow]
    total_capital: Decimal
    total_pnl_today: Decimal
