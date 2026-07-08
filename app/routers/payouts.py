from uuid import UUID

from fastapi import APIRouter, HTTPException
from psycopg2.extras import Json

from app.database import get_cursor
from app.schemas import AllocationOut, PayoutEligibilityOut, PayoutRuleCreate, PayoutRuleOut

router = APIRouter(tags=["payouts"])


@router.post("/payout-rules", response_model=PayoutRuleOut, status_code=201)
def create_payout_rule(body: PayoutRuleCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO payout_rules (account_type, profit_split_pct, min_payout_amount, "
            "payout_frequency, notes, effective_date) "
            "VALUES (%s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE)) "
            "RETURNING id, account_type, profit_split_pct, min_payout_amount, "
            "payout_frequency, notes, effective_date",
            (
                body.account_type,
                body.profit_split_pct,
                body.min_payout_amount,
                body.payout_frequency,
                body.notes,
                body.effective_date,
            ),
        )
        return cur.fetchone()


@router.get("/payout-rules", response_model=list[PayoutRuleOut])
def list_payout_rules(account_type: str | None = None):
    query = (
        "SELECT id, account_type, profit_split_pct, min_payout_amount, "
        "payout_frequency, notes, effective_date FROM payout_rules"
    )
    params: list = []
    if account_type is not None:
        query += " WHERE account_type = %s"
        params.append(account_type)
    query += " ORDER BY account_type, effective_date DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/accounts/{account_id}/payout-eligibility", response_model=PayoutEligibilityOut)
def check_payout_eligibility(account_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "SELECT account_type, capital_base, current_balance FROM account_balances "
            "WHERE account_id = %s",
            (str(account_id),),
        )
        account = cur.fetchone()
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")

        cur.execute(
            "SELECT id, profit_split_pct, min_payout_amount FROM payout_rules "
            "WHERE account_type = %s AND effective_date <= CURRENT_DATE "
            "ORDER BY effective_date DESC LIMIT 1",
            (account["account_type"],),
        )
        rule = cur.fetchone()
        if rule is None:
            raise HTTPException(
                status_code=404,
                detail=f"No payout_rules configured for account_type '{account['account_type']}' yet",
            )

        profit_basis = account["current_balance"] - account["capital_base"]

        eligible = False
        computed_amount = None
        reason = None

        if profit_basis <= 0:
            reason = "No unpaid profit (current balance is at or below capital base)"
        else:
            computed_amount = round(profit_basis * rule["profit_split_pct"], 2)
            if rule["min_payout_amount"] is not None and computed_amount < rule["min_payout_amount"]:
                reason = (
                    f"Computed amount {computed_amount} is below the minimum payout "
                    f"amount {rule['min_payout_amount']}"
                )
            else:
                eligible = True

        computed_from = {
            "profit_basis": str(profit_basis),
            "profit_split_pct": str(rule["profit_split_pct"]),
            "payout_rule_id": str(rule["id"]),
            "current_balance": str(account["current_balance"]),
            "capital_base": str(account["capital_base"]),
        }

        cur.execute(
            "INSERT INTO payout_eligibility_checks "
            "(account_id, eligible, computed_amount, computed_from, reason_if_ineligible) "
            "VALUES (%s, %s, %s, %s, %s) "
            "RETURNING account_id, checked_at, eligible, computed_amount, computed_from, "
            "reason_if_ineligible",
            (str(account_id), eligible, computed_amount, Json(computed_from), reason),
        )
        return cur.fetchone()


@router.get("/accounts/{account_id}/payout-history", response_model=list[AllocationOut])
def get_payout_history(account_id: UUID):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(account_id),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Account not found")

        cur.execute(
            "SELECT id, account_id, type, amount, period_start, period_end, "
            "computed_from, memo, created_at, created_by "
            "FROM allocations WHERE account_id = %s AND type = 'payout' ORDER BY created_at",
            (str(account_id),),
        )
        return cur.fetchall()
