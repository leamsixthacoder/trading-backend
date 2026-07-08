from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import AggregateRiskRuleCreate, AggregateRiskRuleOut, AggregateRiskStatusOut

router = APIRouter(tags=["aggregate-risk"])

SCOPE_FILTERS = {
    "all": "TRUE",
    "funded_only": "account_type IN ('funded_lucid', 'funded_topstep')",
    "personal_only": "account_type IN ('personal_live', 'personal_portfolio')",
}


@router.post("/aggregate-risk-rules", response_model=AggregateRiskRuleOut, status_code=201)
def create_aggregate_risk_rule(body: AggregateRiskRuleCreate):
    if body.scope not in SCOPE_FILTERS:
        raise HTTPException(status_code=400, detail=f"scope must be one of {list(SCOPE_FILTERS)}")

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO aggregate_risk_rules (rule_type, scope, threshold, active) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, rule_type, scope, threshold, active",
            (body.rule_type, body.scope, body.threshold, body.active),
        )
        return cur.fetchone()


@router.get("/aggregate-risk-rules", response_model=list[AggregateRiskRuleOut])
def list_aggregate_risk_rules():
    with get_cursor() as cur:
        cur.execute("SELECT id, rule_type, scope, threshold, active FROM aggregate_risk_rules ORDER BY rule_type")
        return cur.fetchall()


def _total_open_risk(cur, scope_filter: str):
    cur.execute(
        f"SELECT COALESCE(SUM(t.size * t.entry_price), 0) AS total "
        f"FROM trades t JOIN accounts a ON a.id = t.account_id "
        f"WHERE t.exit_time IS NULL AND {scope_filter}"
    )
    return cur.fetchone()["total"]


def _total_daily_pnl(cur, scope_filter: str):
    cur.execute(
        f"SELECT COALESCE(SUM(p.pnl_net), 0) AS total "
        f"FROM account_pnl_by_day p JOIN accounts a ON a.id = p.account_id "
        f"WHERE p.day = date_trunc('day', now()) AND {scope_filter}"
    )
    return cur.fetchone()["total"]


@router.get("/risk/aggregate-status", response_model=AggregateRiskStatusOut)
def get_aggregate_risk_status():
    with get_cursor() as cur:
        total_open_risk = _total_open_risk(cur, SCOPE_FILTERS["all"])
        total_daily_pnl = _total_daily_pnl(cur, SCOPE_FILTERS["all"])

        cur.execute(
            "SELECT id, rule_type, scope, threshold FROM aggregate_risk_rules WHERE active = true"
        )
        rules = cur.fetchall()

        breaches = []
        for rule in rules:
            scope_filter = SCOPE_FILTERS.get(rule["scope"])
            if scope_filter is None:
                continue

            if rule["rule_type"] == "total_open_risk":
                actual = _total_open_risk(cur, scope_filter)
                breached = actual > rule["threshold"]
            elif rule["rule_type"] == "total_daily_loss_all_accounts":
                actual = _total_daily_pnl(cur, scope_filter)
                breached = actual <= -rule["threshold"]
            else:
                continue

            if breached:
                breaches.append(
                    {
                        "rule_id": rule["id"],
                        "rule_type": rule["rule_type"],
                        "scope": rule["scope"],
                        "threshold": rule["threshold"],
                        "actual": actual,
                    }
                )

        return {
            "total_open_risk": total_open_risk,
            "total_daily_pnl": total_daily_pnl,
            "breaches": breaches,
        }
