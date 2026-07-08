import statistics
from uuid import UUID

from fastapi import APIRouter, HTTPException
from psycopg2.extras import Json

from app.database import get_cursor
from app.schemas import (
    BacktestCreate,
    BacktestOut,
    PositionSizingRuleCreate,
    PositionSizingRuleOut,
    StrategyCreate,
    StrategyOut,
    StrategyStatusUpdate,
    StrategyValidationCreate,
    StrategyValidationOut,
)

router = APIRouter(tags=["strategies"])


def _require_strategy_exists(cur, strategy_id: UUID) -> None:
    cur.execute("SELECT 1 FROM strategies WHERE id = %s", (str(strategy_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.post("/strategies", response_model=StrategyOut, status_code=201)
def create_strategy(body: StrategyCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO strategies (name, description, rules) VALUES (%s, %s, %s) "
            "RETURNING id, name, description, rules, status, created_at",
            (body.name, body.description, Json(body.rules)),
        )
        return cur.fetchone()


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(status: str | None = None):
    query = "SELECT id, name, description, rules, status, created_at FROM strategies"
    params: list = []
    if status is not None:
        query += " WHERE status = %s"
        params.append(status)
    query += " ORDER BY created_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.patch("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy_status(strategy_id: UUID, body: StrategyStatusUpdate):
    with get_cursor() as cur:
        _require_strategy_exists(cur, strategy_id)

        if body.status == "live":
            cur.execute(
                "SELECT 1 FROM strategy_validations WHERE strategy_id = %s AND approved = true",
                (str(strategy_id),),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot mark a strategy live without an approved strategy_validations row",
                )

        cur.execute(
            "UPDATE strategies SET status = %s WHERE id = %s "
            "RETURNING id, name, description, rules, status, created_at",
            (body.status, str(strategy_id)),
        )
        return cur.fetchone()


@router.post("/strategies/{strategy_id}/backtests", response_model=BacktestOut, status_code=201)
def run_backtest(strategy_id: UUID, body: BacktestCreate):
    with get_cursor() as cur:
        _require_strategy_exists(cur, strategy_id)

        query = (
            "SELECT pnl_net, exit_time FROM trades "
            "WHERE exit_time IS NOT NULL AND exit_time::date BETWEEN %s AND %s"
        )
        params: list = [body.period_start, body.period_end]
        if body.tags:
            query += " AND tags && %s::text[]"
            params.append(body.tags)
        if body.account_id is not None:
            query += " AND account_id = %s"
            params.append(str(body.account_id))
        query += " ORDER BY exit_time"

        cur.execute(query, params)
        rows = cur.fetchall()

        pnls = [row["pnl_net"] for row in rows]
        total_trades = len(pnls)
        total_pnl = sum(pnls) if pnls else None
        win_rate = (sum(1 for p in pnls if p > 0) / total_trades) if total_trades > 0 else None

        max_drawdown = None
        if pnls:
            cumulative = 0
            peak = 0
            max_dd = 0
            for p in pnls:
                cumulative += p
                peak = max(peak, cumulative)
                max_dd = min(max_dd, cumulative - peak)
            max_drawdown = max_dd

        sharpe_ratio = None
        if total_trades >= 2:
            pnl_floats = [float(p) for p in pnls]
            stdev = statistics.stdev(pnl_floats)
            if stdev > 0:
                sharpe_ratio = statistics.mean(pnl_floats) / stdev

        data_source = f"own_trades:{','.join(body.tags)}" if body.tags else "own_trades:all"
        parameters_snapshot = {
            "tags": body.tags,
            "account_id": str(body.account_id) if body.account_id else None,
            "period_start": str(body.period_start),
            "period_end": str(body.period_end),
        }

        cur.execute(
            "INSERT INTO backtests (strategy_id, period_start, period_end, data_source, "
            "total_trades, win_rate, total_pnl, max_drawdown, sharpe_ratio, parameters_snapshot) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, strategy_id, period_start, period_end, data_source, total_trades, "
            "win_rate, total_pnl, max_drawdown, sharpe_ratio, parameters_snapshot, created_at",
            (
                str(strategy_id),
                body.period_start,
                body.period_end,
                data_source,
                total_trades,
                win_rate,
                total_pnl,
                max_drawdown,
                sharpe_ratio,
                Json(parameters_snapshot),
            ),
        )
        return cur.fetchone()


@router.get("/strategies/{strategy_id}/backtests", response_model=list[BacktestOut])
def list_backtests(strategy_id: UUID):
    with get_cursor() as cur:
        _require_strategy_exists(cur, strategy_id)
        cur.execute(
            "SELECT id, strategy_id, period_start, period_end, data_source, total_trades, "
            "win_rate, total_pnl, max_drawdown, sharpe_ratio, parameters_snapshot, created_at "
            "FROM backtests WHERE strategy_id = %s ORDER BY created_at DESC",
            (str(strategy_id),),
        )
        return cur.fetchall()


@router.get("/backtests/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, strategy_id, period_start, period_end, data_source, total_trades, "
            "win_rate, total_pnl, max_drawdown, sharpe_ratio, parameters_snapshot, created_at "
            "FROM backtests WHERE id = %s",
            (str(backtest_id),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Backtest not found")
        return row


@router.post("/strategies/{strategy_id}/validate", response_model=StrategyValidationOut, status_code=201)
def validate_strategy(strategy_id: UUID, body: StrategyValidationCreate):
    with get_cursor() as cur:
        _require_strategy_exists(cur, strategy_id)

        cur.execute("SELECT 1 FROM backtests WHERE id = %s AND strategy_id = %s",
                     (str(body.backtest_id), str(strategy_id)))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Backtest not found for this strategy")

        cur.execute(
            "INSERT INTO strategy_validations (strategy_id, backtest_id, approved, criteria_met, notes) "
            "VALUES (%s, %s, %s, %s, %s) "
            "RETURNING id, strategy_id, backtest_id, approved, criteria_met, notes, created_at",
            (str(strategy_id), str(body.backtest_id), body.approved, Json(body.criteria_met), body.notes),
        )
        return cur.fetchone()


@router.get("/strategies/{strategy_id}/validation-status")
def get_validation_status(strategy_id: UUID):
    with get_cursor() as cur:
        _require_strategy_exists(cur, strategy_id)
        cur.execute(
            "SELECT id, approved, created_at FROM strategy_validations "
            "WHERE strategy_id = %s ORDER BY created_at DESC LIMIT 1",
            (str(strategy_id),),
        )
        latest = cur.fetchone()
        cur.execute(
            "SELECT 1 FROM strategy_validations WHERE strategy_id = %s AND approved = true LIMIT 1",
            (str(strategy_id),),
        )
        has_approval = cur.fetchone() is not None
        return {"strategy_id": strategy_id, "has_approval": has_approval, "latest_validation": latest}


@router.post("/position-sizing-rules", response_model=PositionSizingRuleOut, status_code=201)
def create_position_sizing_rule(body: PositionSizingRuleCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO position_sizing_rules (strategy_id, account_id, method, parameters) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, strategy_id, account_id, method, parameters, created_at",
            (
                str(body.strategy_id) if body.strategy_id else None,
                str(body.account_id) if body.account_id else None,
                body.method,
                Json(body.parameters),
            ),
        )
        return cur.fetchone()


@router.get("/position-sizing-rules", response_model=list[PositionSizingRuleOut])
def list_position_sizing_rules(strategy_id: UUID | None = None, account_id: UUID | None = None):
    query = "SELECT id, strategy_id, account_id, method, parameters, created_at FROM position_sizing_rules"
    params: list = []
    conditions = []
    if strategy_id is not None:
        conditions.append("strategy_id = %s")
        params.append(str(strategy_id))
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
