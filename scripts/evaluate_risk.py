"""Evaluate active risk_rules against today's trade data and insert
risk_alerts on breach. Also evaluates active aggregate_risk_rules
(Phase 4) across accounts and prints any breaches - there is no
aggregate-alerts table to persist into, so those are surfaced via
script output only, same "surface don't enforce" spirit as the
per-account alerts. Run manually or via cron/after each CSV import.

Alerts are surfaced, not enforced: this never blocks a trade or touches
positions, it only records that a threshold was crossed. Never dedupes —
each run that finds a breach inserts a new row, same as the append-only
allocations ledger.

Uses DATABASE_URL from .env (the live app DB), not a local DSN default.
"""

import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def _accounts_for_rule(cur, rule):
    if rule["account_id"] is not None:
        return [rule["account_id"]]
    cur.execute("SELECT id FROM accounts WHERE status = 'active'")
    return [row["id"] for row in cur.fetchall()]


def _evaluate_max_daily_loss(cur, account_id, threshold):
    cur.execute(
        "SELECT COALESCE(pnl_net, 0) AS pnl_net FROM account_pnl_by_day "
        "WHERE account_id = %s AND day = date_trunc('day', now())",
        (account_id,),
    )
    row = cur.fetchone()
    actual = row["pnl_net"] if row else 0
    breached = actual <= -threshold
    return breached, actual


def _evaluate_max_trades_per_day(cur, account_id, threshold):
    cur.execute(
        "SELECT COUNT(*) AS trade_count FROM trades "
        "WHERE account_id = %s AND date_trunc('day', entry_time) = date_trunc('day', now())",
        (account_id,),
    )
    actual = cur.fetchone()["trade_count"]
    breached = actual > threshold
    return breached, actual


def _evaluate_max_position_size(cur, account_id, threshold):
    cur.execute(
        "SELECT MAX(size) AS max_size FROM trades "
        "WHERE account_id = %s AND date_trunc('day', entry_time) = date_trunc('day', now())",
        (account_id,),
    )
    row = cur.fetchone()
    actual = row["max_size"] if row and row["max_size"] is not None else 0
    breached = actual > threshold
    return breached, actual


EVALUATORS = {
    "max_daily_loss": _evaluate_max_daily_loss,
    "max_trades_per_day": _evaluate_max_trades_per_day,
    "max_position_size": _evaluate_max_position_size,
}

AGGREGATE_SCOPE_FILTERS = {
    "all": "TRUE",
    "funded_only": "account_type IN ('funded_lucid', 'funded_topstep')",
    "personal_only": "account_type IN ('personal_live', 'personal_portfolio')",
}


def _aggregate_total_open_risk(cur, scope_filter):
    cur.execute(
        f"SELECT COALESCE(SUM(t.size * t.entry_price), 0) AS total "
        f"FROM trades t JOIN accounts a ON a.id = t.account_id "
        f"WHERE t.exit_time IS NULL AND {scope_filter}"
    )
    return cur.fetchone()["total"]


def _aggregate_total_daily_pnl(cur, scope_filter):
    cur.execute(
        f"SELECT COALESCE(SUM(p.pnl_net), 0) AS total "
        f"FROM account_pnl_by_day p JOIN accounts a ON a.id = p.account_id "
        f"WHERE p.day = date_trunc('day', now()) AND {scope_filter}"
    )
    return cur.fetchone()["total"]


def _evaluate_aggregate_rules(cur):
    cur.execute(
        "SELECT id, rule_type, scope, threshold FROM aggregate_risk_rules WHERE active = true"
    )
    rules = cur.fetchall()

    breaches = 0
    for rule in rules:
        scope_filter = AGGREGATE_SCOPE_FILTERS.get(rule["scope"])
        if scope_filter is None:
            print(f"Skipping aggregate rule {rule['id']} with unknown scope '{rule['scope']}'")
            continue

        if rule["rule_type"] == "total_open_risk":
            actual = _aggregate_total_open_risk(cur, scope_filter)
            breached = actual > rule["threshold"]
        elif rule["rule_type"] == "total_daily_loss_all_accounts":
            actual = _aggregate_total_daily_pnl(cur, scope_filter)
            breached = actual <= -rule["threshold"]
        else:
            print(f"Skipping unknown aggregate rule_type '{rule['rule_type']}' (rule {rule['id']})")
            continue

        if breached:
            breaches += 1
            print(
                f"AGGREGATE ALERT: rule {rule['id']} ('{rule['rule_type']}', scope="
                f"'{rule['scope']}') breached - actual={actual} threshold={rule['threshold']}"
            )

    return breaches


def main():
    conn = psycopg2.connect(DATABASE_URL)
    alerts_inserted = 0
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, account_id, rule_type, threshold FROM risk_rules WHERE active = true"
            )
            rules = cur.fetchall()

            for rule in rules:
                evaluator = EVALUATORS.get(rule["rule_type"])
                if evaluator is None:
                    print(f"Skipping unknown rule_type '{rule['rule_type']}' (rule {rule['id']})")
                    continue

                for account_id in _accounts_for_rule(cur, rule):
                    breached, actual = evaluator(cur, account_id, rule["threshold"])
                    if not breached:
                        continue

                    cur.execute(
                        "INSERT INTO risk_alerts "
                        "(account_id, risk_rule_id, actual_value, threshold_value) "
                        "VALUES (%s, %s, %s, %s) RETURNING id",
                        (account_id, rule["id"], actual, rule["threshold"]),
                    )
                    alert_id = cur.fetchone()["id"]
                    alerts_inserted += 1
                    print(
                        f"ALERT {alert_id}: account {account_id} breached "
                        f"'{rule['rule_type']}' - actual={actual} threshold={rule['threshold']}"
                    )

            aggregate_breaches = _evaluate_aggregate_rules(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"Done. {alerts_inserted} alert(s) inserted, {aggregate_breaches} aggregate breach(es).")
    return alerts_inserted


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
