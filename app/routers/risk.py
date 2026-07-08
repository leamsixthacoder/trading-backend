from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import RiskAlertOut, RiskRuleCreate, RiskRuleOut

router = APIRouter(tags=["risk"])


@router.post("/risk-rules", response_model=RiskRuleOut, status_code=201)
def create_risk_rule(body: RiskRuleCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO risk_rules (account_id, rule_type, threshold, active) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, account_id, rule_type, threshold, active, created_at",
            (
                str(body.account_id) if body.account_id else None,
                body.rule_type,
                body.threshold,
                body.active,
            ),
        )
        return cur.fetchone()


@router.get("/risk-rules", response_model=list[RiskRuleOut])
def list_risk_rules(account_id: UUID | None = None):
    query = "SELECT id, account_id, rule_type, threshold, active, created_at FROM risk_rules"
    params: list = []
    if account_id is not None:
        query += " WHERE account_id = %s"
        params.append(str(account_id))
    query += " ORDER BY created_at"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/risk-alerts", response_model=list[RiskAlertOut])
def list_risk_alerts(account_id: UUID | None = None, acknowledged: bool | None = None):
    query = (
        "SELECT id, account_id, risk_rule_id, triggered_at, actual_value, "
        "threshold_value, acknowledged FROM risk_alerts"
    )
    params: list = []
    conditions = []
    if account_id is not None:
        conditions.append("account_id = %s")
        params.append(str(account_id))
    if acknowledged is not None:
        conditions.append("acknowledged = %s")
        params.append(acknowledged)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY triggered_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.patch("/risk-alerts/{alert_id}/acknowledge", response_model=RiskAlertOut)
def acknowledge_risk_alert(alert_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE risk_alerts SET acknowledged = true WHERE id = %s "
            "RETURNING id, account_id, risk_rule_id, triggered_at, actual_value, "
            "threshold_value, acknowledged",
            (str(alert_id),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Risk alert not found")
        return row
