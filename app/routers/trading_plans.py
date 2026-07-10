from datetime import date
from uuid import UUID

import psycopg2
from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import (
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemUpdate,
    DailyLogOut,
    DailyLogSummaryOut,
    DailyLogUpdate,
    TradingPlanCreate,
    TradingPlanOut,
    TradingPlanStrategyCreate,
    TradingPlanStrategyOut,
    TradingPlanUpdate,
)

router = APIRouter(prefix="/trading-plans", tags=["trading-plans"])

PLAN_COLUMNS = "id, name, description, account_id, account_group_id, status, created_at, updated_at"


def _require_plan_exists(cur, plan_id: UUID) -> None:
    cur.execute("SELECT 1 FROM trading_plans WHERE id = %s", (str(plan_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Trading plan not found")


def _fetch_daily_log(cur, plan_id: UUID, log_date: date) -> dict:
    cur.execute(
        "SELECT notes FROM trading_plan_daily_logs WHERE plan_id = %s AND log_date = %s",
        (str(plan_id), log_date),
    )
    log_row = cur.fetchone()

    cur.execute(
        "SELECT ci.id AS checklist_item_id, ci.label, ci.sort_order, "
        "COALESCE(li.checked, false) AS checked, li.checked_at "
        "FROM trading_plan_checklist_items ci "
        "LEFT JOIN trading_plan_daily_logs dl ON dl.plan_id = ci.plan_id AND dl.log_date = %s "
        "LEFT JOIN trading_plan_daily_log_items li "
        "  ON li.daily_log_id = dl.id AND li.checklist_item_id = ci.id "
        "WHERE ci.plan_id = %s "
        "ORDER BY ci.sort_order, ci.created_at",
        (log_date, str(plan_id)),
    )
    items = cur.fetchall()

    return {
        "plan_id": plan_id,
        "log_date": log_date,
        "notes": log_row["notes"] if log_row else None,
        "items": items,
    }


@router.post("", response_model=TradingPlanOut, status_code=201)
def create_trading_plan(body: TradingPlanCreate):
    if (body.account_id is None) == (body.account_group_id is None):
        raise HTTPException(
            status_code=400,
            detail="Exactly one of account_id or account_group_id must be set",
        )

    with get_cursor() as cur:
        if body.account_id is not None:
            cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(body.account_id),))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Account not found")
        else:
            cur.execute("SELECT 1 FROM account_groups WHERE id = %s", (str(body.account_group_id),))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Account group not found")

        cur.execute(
            f"INSERT INTO trading_plans (name, description, account_id, account_group_id) "
            f"VALUES (%s, %s, %s, %s) RETURNING {PLAN_COLUMNS}",
            (
                body.name,
                body.description,
                str(body.account_id) if body.account_id else None,
                str(body.account_group_id) if body.account_group_id else None,
            ),
        )
        return cur.fetchone()


@router.get("", response_model=list[TradingPlanOut])
def list_trading_plans(
    account_id: UUID | None = None,
    account_group_id: UUID | None = None,
    status: str | None = None,
):
    query = f"SELECT {PLAN_COLUMNS} FROM trading_plans"
    params: list = []
    conditions = []
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if account_group_id is not None:
        conditions.append("account_group_id = %s")
        params.append(str(account_group_id))
    if status is not None:
        conditions.append("status = %s")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/{plan_id}", response_model=TradingPlanOut)
def get_trading_plan(plan_id: UUID):
    with get_cursor() as cur:
        cur.execute(f"SELECT {PLAN_COLUMNS} FROM trading_plans WHERE id = %s", (str(plan_id),))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Trading plan not found")
        return row


@router.patch("/{plan_id}", response_model=TradingPlanOut)
def update_trading_plan(plan_id: UUID, body: TradingPlanUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{key} = %s" for key in fields)
    params = list(fields.values()) + [str(plan_id)]

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE trading_plans SET {set_clause}, updated_at = now() "
            f"WHERE id = %s RETURNING {PLAN_COLUMNS}",
            params,
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Trading plan not found")
        return row


@router.delete("/{plan_id}", status_code=204)
def delete_trading_plan(plan_id: UUID):
    with get_cursor() as cur:
        cur.execute("DELETE FROM trading_plans WHERE id = %s", (str(plan_id),))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Trading plan not found")


@router.get("/{plan_id}/strategies", response_model=list[TradingPlanStrategyOut])
def list_plan_strategies(plan_id: UUID):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)
        cur.execute(
            "SELECT ps.plan_id, ps.strategy_id, s.name AS strategy_name, "
            "s.status AS strategy_status, ps.added_at "
            "FROM trading_plan_strategies ps JOIN strategies s ON s.id = ps.strategy_id "
            "WHERE ps.plan_id = %s ORDER BY ps.added_at",
            (str(plan_id),),
        )
        return cur.fetchall()


@router.post("/{plan_id}/strategies", response_model=TradingPlanStrategyOut, status_code=201)
def attach_plan_strategy(plan_id: UUID, body: TradingPlanStrategyCreate):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)
        cur.execute("SELECT 1 FROM strategies WHERE id = %s", (str(body.strategy_id),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        try:
            cur.execute(
                "INSERT INTO trading_plan_strategies (plan_id, strategy_id) VALUES (%s, %s) "
                "RETURNING plan_id, strategy_id, added_at",
                (str(plan_id), str(body.strategy_id)),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Strategy is already attached to this plan")
        row = cur.fetchone()

        cur.execute(
            "SELECT name, status FROM strategies WHERE id = %s", (str(body.strategy_id),)
        )
        strategy = cur.fetchone()
        return {
            "plan_id": row["plan_id"],
            "strategy_id": row["strategy_id"],
            "strategy_name": strategy["name"],
            "strategy_status": strategy["status"],
            "added_at": row["added_at"],
        }


@router.delete("/{plan_id}/strategies/{strategy_id}", status_code=204)
def detach_plan_strategy(plan_id: UUID, strategy_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM trading_plan_strategies WHERE plan_id = %s AND strategy_id = %s",
            (str(plan_id), str(strategy_id)),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Strategy is not attached to this plan")


@router.get("/{plan_id}/checklist-items", response_model=list[ChecklistItemOut])
def list_checklist_items(plan_id: UUID):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)
        cur.execute(
            "SELECT id, plan_id, label, sort_order, created_at FROM trading_plan_checklist_items "
            "WHERE plan_id = %s ORDER BY sort_order, created_at",
            (str(plan_id),),
        )
        return cur.fetchall()


@router.post("/{plan_id}/checklist-items", response_model=ChecklistItemOut, status_code=201)
def create_checklist_item(plan_id: UUID, body: ChecklistItemCreate):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)
        cur.execute(
            "INSERT INTO trading_plan_checklist_items (plan_id, label, sort_order) "
            "VALUES (%s, %s, %s) RETURNING id, plan_id, label, sort_order, created_at",
            (str(plan_id), body.label, body.sort_order),
        )
        return cur.fetchone()


@router.patch("/{plan_id}/checklist-items/{item_id}", response_model=ChecklistItemOut)
def update_checklist_item(plan_id: UUID, item_id: UUID, body: ChecklistItemUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{key} = %s" for key in fields)
    params = list(fields.values()) + [str(item_id), str(plan_id)]

    with get_cursor() as cur:
        cur.execute(
            f"UPDATE trading_plan_checklist_items SET {set_clause} "
            f"WHERE id = %s AND plan_id = %s "
            f"RETURNING id, plan_id, label, sort_order, created_at",
            params,
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        return row


@router.delete("/{plan_id}/checklist-items/{item_id}", status_code=204)
def delete_checklist_item(plan_id: UUID, item_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM trading_plan_checklist_items WHERE id = %s AND plan_id = %s",
            (str(item_id), str(plan_id)),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Checklist item not found")


@router.get("/{plan_id}/daily-logs", response_model=list[DailyLogSummaryOut])
def list_daily_logs(plan_id: UUID, start: date, end: date):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)
        cur.execute(
            "SELECT dl.log_date, dl.notes, "
            "COUNT(ci.id) AS total_items, "
            "COUNT(*) FILTER (WHERE li.checked) AS checked_items "
            "FROM trading_plan_daily_logs dl "
            "JOIN trading_plan_checklist_items ci ON ci.plan_id = dl.plan_id "
            "LEFT JOIN trading_plan_daily_log_items li "
            "  ON li.daily_log_id = dl.id AND li.checklist_item_id = ci.id "
            "WHERE dl.plan_id = %s AND dl.log_date BETWEEN %s AND %s "
            "GROUP BY dl.id, dl.log_date, dl.notes "
            "ORDER BY dl.log_date",
            (str(plan_id), start, end),
        )
        return cur.fetchall()


@router.get("/{plan_id}/daily-logs/{log_date}", response_model=DailyLogOut)
def get_daily_log(plan_id: UUID, log_date: date):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)
        return _fetch_daily_log(cur, plan_id, log_date)


@router.put("/{plan_id}/daily-logs/{log_date}", response_model=DailyLogOut)
def upsert_daily_log(plan_id: UUID, log_date: date, body: DailyLogUpdate):
    with get_cursor() as cur:
        _require_plan_exists(cur, plan_id)

        cur.execute(
            "INSERT INTO trading_plan_daily_logs (plan_id, log_date, notes) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (plan_id, log_date) DO UPDATE SET notes = EXCLUDED.notes "
            "RETURNING id",
            (str(plan_id), log_date, body.notes),
        )
        daily_log_id = cur.fetchone()["id"]

        for item in body.items:
            cur.execute("SELECT 1 FROM trading_plan_checklist_items WHERE id = %s AND plan_id = %s",
                        (str(item.checklist_item_id), str(plan_id)))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Checklist item not found for this plan")

            cur.execute(
                "INSERT INTO trading_plan_daily_log_items "
                "(daily_log_id, checklist_item_id, checked, checked_at) "
                "VALUES (%s, %s, %s, CASE WHEN %s THEN now() ELSE NULL END) "
                "ON CONFLICT (daily_log_id, checklist_item_id) "
                "DO UPDATE SET checked = EXCLUDED.checked, checked_at = EXCLUDED.checked_at",
                (str(daily_log_id), str(item.checklist_item_id), item.checked, item.checked),
            )

        return _fetch_daily_log(cur, plan_id, log_date)
