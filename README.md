# trading-backend

Backend for a personal trading management system — solo/personal use, not
multi-tenant. Full brief and phase plan live in the `Management/` planning
repo alongside this one; see that repo's `CONTEXT.md` for the full picture.

## Status

- **Phase 1 (done):** accounts/trades/allocations schema, deployed to Neon.
  `account_balances` is the only place balance is ever read from — no stored
  balance column exists anywhere, by design. `account_status_history` logs
  every status change automatically via trigger.
- **Phase 2 (in progress):** FastAPI app in `app/`, exposing read endpoints
  over the views created in Phase 1.

## Non-negotiable rules (don't let these drift)

- No stored `balance` column, ever. Always read from the `account_balances` view.
- `trades.account_id` is NOT NULL everywhere; every query filters by account_id.
- `allocations` is insert-only — DB trigger rejects UPDATE/DELETE. Fix mistakes
  with a `correction` row, never by editing history.
- Never infer `account_id` from a CSV file — always passed explicitly.
- `--platform` is the CSV format (ninjatrader/tradestation/topstepx), not the
  fund brand (Lucid/Topstep) — `--account-id` is what determines the account.

## Local setup

```
python -m pip install -r scripts/requirements.txt
```

Create `.env` (see `.env.example`) with your Neon `DATABASE_URL`.

## Running migrations

No local `psql` required — any Postgres client works. Run
`migrations/001` through `005` in order against `DATABASE_URL`.

## CSV import

```
python scripts/import_csv.py --account-id <uuid> --platform ninjatrader \
    --file path/to/export.csv --dsn "$DATABASE_URL"
```

Re-running the same file should report 0 inserted, all skipped as duplicates.
