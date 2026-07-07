# Phase 1 Build Instructions — Trading Management System

## Read these files first, in this order

1. `CONTEXT.md` — the full original project brief, so Claude Code understands
   where this system is headed, not just what Phase 1 is.
2. `TECH_STACK.md` — stack choice and free hosting reasoning.
3. `backend-instructions/BACKEND_SETUP.md` — if working in the backend repo.
4. `frontend-instructions/FRONTEND_SETUP.md` — if working in the frontend repo.

This is a **solo, personal-use project** — one user, not a multi-tenant app —
and the backend and frontend are **two separate codebases/repos**. Don't
assume a monorepo structure.

## Goal of Phase 1

Stand up the foundation that everything else depends on: accounts, trades, and an
append-only allocations ledger, with account separation enforced at the database
level (not just application logic). No journal UI, no dashboard, no strategy engine
yet — those come in Phase 2/3 and are cheap to build once this is right.

## What's in this package

```
migrations/
  001_create_accounts.sql      -- accounts table, account_type/status enums
  002_create_trades.sql        -- csv_imports + trades tables, dedup constraint
  003_create_allocations.sql   -- append-only allocations ledger, DB-enforced
  004_create_views.sql         -- account_balances, pnl_by_day, pnl_by_month
  005_seed_accounts.sql        -- pre-filled with your 5 Lucid Flex + 2 Topstep accounts
scripts/
  import_csv.py                -- CSV validation + import pipeline
  requirements.txt
```

## Steps for Claude Code

1. **Set up Postgres.** Local instance is fine for now — a hosted DB isn't needed
   until you're ready to deploy something remotely accessible.

2. **Run migrations in order** (001 through 005). Each file has comments explaining
   *why* a constraint exists, not just what it does — read them, don't just execute.

3. **Edit `005_seed_accounts.sql` before running it** — confirm the Lucid Flex and
   Topstep capital bases match what's actually funded right now, and uncomment/fill
   in your personal live account(s) with real capital_base values.

4. **Install script deps**: `pip install -r scripts/requirements.txt`

5. **Test the import pipeline against one real CSV export** before trusting it
   broadly. `--platform` is the CSV *format* (which execution software
   produced it), not which fund it belongs to — `--account-id` is what ties
   the trades to the correct Lucid/Topstep/personal account. For example, if
   you trade a Topstep account through NinjaTrader:
   ```
   python scripts/import_csv.py --account-id <topstep-account-uuid> \
       --platform ninjatrader --file path/to/export.csv
   ```
   Supported `--platform` values right now: `tradestation`, `ninjatrader`,
   `topstepx` (Topstep's own native export, if you use TopstepX directly
   instead of NinjaTrader/Tradovate as your execution platform).
   Check the printed summary (inserted / skipped-duplicate / validation errors).
   Re-run the same file a second time — it should report 0 inserted, all skipped
   as duplicates. That's the dedup constraint working correctly.

6. **If a real CSV's columns don't match `PLATFORM_MAPS`** in `import_csv.py`,
   update the mapping for that platform — this is expected on the first real
   import, broker export formats are rarely exactly as documented.

## The non-negotiable rules for this schema (don't let these drift as you build)

- **No account ever gets a stored `balance` column.** Balance is always
  `capital_base + trades.pnl_net (closed trades only) + allocations.amount`,
  read from `account_balances`. If a future feature seems to need a stored
  balance, it doesn't — query the view.
- **`trades.account_id` is NOT NULL everywhere**, no exceptions. Every query
  touching trades filters by account_id. This is the actual anti-leak guarantee.
- **`allocations` is insert-only.** The DB trigger will reject UPDATE/DELETE.
  Mistakes get fixed with a `correction` row that references what it's fixing
  in `memo`, not by editing history.
- **Never infer `account_id` from a CSV file.** It's always passed explicitly
  by whoever runs the import. The file doesn't know which account it belongs to;
  you do.
- **`--platform` is the CSV format, not the fund brand.** Lucid Flex and
  Topstep aren't CSV formats — they're accounts you trade through an execution
  platform (NinjaTrader, Tradovate, TopstepX). The same `--platform ninjatrader`
  import can go into a Lucid account, a Topstep account, or a personal account;
  `--account-id` is the only thing that determines which.

## Definition of done for Phase 1

- [ ] All 5 migrations run cleanly against a fresh database
- [ ] All 7 current accounts (5 Lucid Flex + 2 Topstep) seeded with correct capital
- [ ] At least one personal live account added
- [ ] One real CSV from each platform you actually use imported successfully
- [ ] Re-importing the same file is a safe no-op (verified duplicate skip)
- [ ] `SELECT * FROM account_balances;` returns correct, separated balances per account

Once that's true, Phase 2 (journal UI + dashboard) is just building read/write
views on top of data that's already trustworthy — that's the payoff of getting
this part right first.
