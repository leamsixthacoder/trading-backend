# BACKEND_SETUP.md — Phase 1

This is its own repo (`trading-backend` or whatever you name it). Read
`CONTEXT.md` first for the full application picture, then follow this file.

## Stack
Python + FastAPI, Postgres (hosted free on Neon), psycopg2 for the import
script. See `TECH_STACK.md` for reasoning.

## Steps

1. **Create a free Neon Postgres database** at neon.tech. Copy the connection
   string it gives you — you'll need it as `DATABASE_URL`.

2. **Create `.env`** (not committed) in the repo root:
   ```
   DATABASE_URL=postgresql://<user>:<password>@<neon-host>/<dbname>?sslmode=require
   ```

3. **Run the migrations in order** against that Neon database:
   ```
   psql "$DATABASE_URL" -f migrations/001_create_accounts.sql
   psql "$DATABASE_URL" -f migrations/002_create_trades.sql
   psql "$DATABASE_URL" -f migrations/003_create_allocations.sql
   psql "$DATABASE_URL" -f migrations/004_create_views.sql
   ```

4. **Edit `migrations/005_seed_accounts.sql`** with your real capital_base
   numbers and personal account(s), then run it too.

5. **Install script deps**: `pip install -r scripts/requirements.txt`

6. **Test the CSV import** against one real export before trusting it broadly.
   `--platform` is the CSV format (NinjaTrader/TradeStation/TopstepX-native),
   independent of which account the trades belong to:
   ```
   python scripts/import_csv.py --account-id <uuid> --platform ninjatrader \
       --file path/to/export.csv --dsn "$DATABASE_URL"
   ```
   Re-run the same file — it should report 0 inserted, all skipped as
   duplicates. On first real use per platform, compare the actual CSV header
   row against `PLATFORM_MAPS` in `import_csv.py` — export formats vary by
   account settings and are best treated as needing a one-time check, not
   assumed correct out of the box.

7. **Phase 2 note (don't build yet, just know it's coming):** once Phase 1 is
   verified, the FastAPI app goes in `app/` and exposes endpoints like
   `GET /accounts/:id/balance` reading from the `account_balances` view —
   never a stored balance field. CORS will need to allow the frontend's
   deployed URL once that exists.

## Deploying free (once Phase 1 is verified locally)

1. Push this repo to GitHub.
2. On Render: New → Web Service → connect the repo.
3. Set the `DATABASE_URL` environment variable in Render's dashboard (same
   Neon connection string, don't commit it to git).
4. Build command: `pip install -r requirements.txt` (once the FastAPI app
   exists in Phase 2 — for now, Phase 1 has no running service, just scripts
   run manually against the DB).

## Definition of done for backend Phase 1

- [ ] Neon database created, connection string in `.env`
- [ ] All 4 migrations run cleanly
- [ ] All 7 current accounts + at least 1 personal account seeded
- [ ] One real CSV per platform imported successfully
- [ ] Re-import of the same file is a safe no-op
- [ ] `SELECT * FROM account_balances;` returns correct, separated balances
