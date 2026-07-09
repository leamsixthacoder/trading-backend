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


TradeDirection = Literal["long", "short"]


class TradeOut(BaseModel):
    id: UUID
    account_id: UUID
    import_batch_id: UUID | None
    source_platform: str
    external_trade_id: str
    symbol: str
    direction: TradeDirection
    size: Decimal
    entry_price: Decimal
    exit_price: Decimal | None
    entry_time: datetime
    exit_time: datetime | None
    fees: Decimal
    pnl_gross: Decimal | None
    pnl_net: Decimal
    tags: list[str]
    notes: str | None
    created_at: datetime


class TradeCreate(BaseModel):
    account_id: UUID
    symbol: str
    direction: TradeDirection
    size: Decimal
    entry_price: Decimal
    exit_price: Decimal | None = None
    entry_time: datetime
    exit_time: datetime | None = None
    fees: Decimal = Decimal("0")
    pnl_gross: Decimal | None = None
    tags: list[str] = []
    notes: str | None = None
    external_trade_id: str | None = None


class TradeUpdate(BaseModel):
    symbol: str | None = None
    direction: TradeDirection | None = None
    size: Decimal | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    fees: Decimal | None = None
    pnl_gross: Decimal | None = None
    tags: list[str] | None = None
    notes: str | None = None


class CsvImportRowError(BaseModel):
    row_number: int
    field: str
    message: str


class CsvImportPreviewRow(BaseModel):
    row_number: int
    external_trade_id: str
    symbol: str
    direction: TradeDirection
    size: Decimal
    entry_price: Decimal
    exit_price: Decimal | None
    entry_time: datetime
    exit_time: datetime | None
    fees: Decimal
    pnl_gross: Decimal | None
    is_duplicate: bool


class CsvImportPreviewOut(BaseModel):
    platform: str
    total_rows: int
    valid_count: int
    duplicate_count: int
    error_count: int
    rows: list[CsvImportPreviewRow]
    errors: list[CsvImportRowError]


class CsvImportOut(BaseModel):
    id: UUID
    account_id: UUID
    source_platform: str
    filename: str
    imported_at: datetime
    row_count: int
    rows_inserted: int
    rows_skipped_dupe: int
    status: str
    validation_errors: list[dict]


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


StrategyStatus = Literal["draft", "backtesting", "validated", "live", "retired"]


class StrategyOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    rules: dict
    status: StrategyStatus
    created_at: datetime


class StrategyCreate(BaseModel):
    name: str
    description: str | None = None
    rules: dict


class StrategyStatusUpdate(BaseModel):
    status: StrategyStatus


class PositionSizingRuleOut(BaseModel):
    id: UUID
    strategy_id: UUID | None
    account_id: UUID | None
    method: str
    parameters: dict
    created_at: datetime


class PositionSizingRuleCreate(BaseModel):
    strategy_id: UUID | None = None
    account_id: UUID | None = None
    method: str
    parameters: dict = {}


class BacktestOut(BaseModel):
    id: UUID
    strategy_id: UUID
    period_start: date
    period_end: date
    data_source: str
    total_trades: int
    win_rate: float | None
    total_pnl: Decimal | None
    max_drawdown: Decimal | None
    sharpe_ratio: float | None
    parameters_snapshot: dict
    created_at: datetime


class BacktestCreate(BaseModel):
    period_start: date
    period_end: date
    tags: list[str] = []
    account_id: UUID | None = None


class StrategyValidationOut(BaseModel):
    id: UUID
    strategy_id: UUID
    backtest_id: UUID
    approved: bool
    criteria_met: dict
    notes: str | None
    created_at: datetime


class StrategyValidationCreate(BaseModel):
    backtest_id: UUID
    approved: bool
    criteria_met: dict = {}
    notes: str | None = None


class HoldingOut(BaseModel):
    id: UUID
    account_id: UUID
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    acquired_date: date
    asset_class: str
    created_at: datetime


class HoldingCreate(BaseModel):
    account_id: UUID
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    acquired_date: date
    asset_class: str = "equity"


class HoldingUpdate(BaseModel):
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    asset_class: str | None = None


class PortfolioSnapshotOut(BaseModel):
    id: UUID
    account_id: UUID
    snapshot_date: date
    total_value: Decimal
    holdings_detail: dict
    created_at: datetime


class PortfolioSnapshotCreate(BaseModel):
    account_id: UUID
    snapshot_date: date
    total_value: Decimal
    holdings_detail: dict = {}


class PortfolioReturnOut(BaseModel):
    account_id: UUID
    period: str
    start_date: date
    end_date: date
    start_value: Decimal
    end_value: Decimal
    return_pct: float


class PayoutRuleOut(BaseModel):
    id: UUID
    account_type: str
    profit_split_pct: Decimal
    min_payout_amount: Decimal | None
    payout_frequency: str | None
    notes: str | None
    effective_date: date


class PayoutRuleCreate(BaseModel):
    account_type: str
    profit_split_pct: Decimal
    min_payout_amount: Decimal | None = None
    payout_frequency: str | None = None
    notes: str | None = None
    effective_date: date | None = None


class PayoutEligibilityOut(BaseModel):
    account_id: UUID
    checked_at: datetime
    eligible: bool
    computed_amount: Decimal | None
    computed_from: dict
    reason_if_ineligible: str | None


class AggregateRiskRuleOut(BaseModel):
    id: UUID
    rule_type: str
    scope: str
    threshold: Decimal
    active: bool


class AggregateRiskRuleCreate(BaseModel):
    rule_type: str
    scope: str
    threshold: Decimal
    active: bool = True


class AggregateRiskBreach(BaseModel):
    rule_id: UUID
    rule_type: str
    scope: str
    threshold: Decimal
    actual: Decimal


class AggregateRiskStatusOut(BaseModel):
    total_open_risk: Decimal
    total_daily_pnl: Decimal
    breaches: list[AggregateRiskBreach]


class EmotionalStateLogOut(BaseModel):
    id: UUID
    logged_at: datetime
    account_id: UUID | None
    state_tags: list[str]
    intensity: int | None
    note: str | None


class EmotionalStateLogCreate(BaseModel):
    account_id: UUID | None = None
    state_tags: list[str] = []
    intensity: int | None = None
    note: str | None = None


class TradeReviewOut(BaseModel):
    id: UUID
    trade_id: UUID | None
    what_happened: str | None
    what_went_well: str | None
    what_to_change: str | None
    created_at: datetime


class TradeReviewCreate(BaseModel):
    trade_id: UUID | None = None
    what_happened: str | None = None
    what_went_well: str | None = None
    what_to_change: str | None = None


AccountRuleType = Literal["profit_target", "daily_loss_limit", "max_loss_limit"]


class AccountRuleOut(BaseModel):
    id: UUID
    account_id: UUID
    rule_type: AccountRuleType
    threshold: Decimal
    created_at: datetime
    updated_at: datetime


class AccountRuleCreate(BaseModel):
    rule_type: AccountRuleType
    threshold: Decimal


class AccountRuleUpdate(BaseModel):
    threshold: Decimal


class QuoteOut(BaseModel):
    symbol: str
    price: Decimal | None
    as_of: datetime | None
    error: str | None
