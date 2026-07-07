# Project Context — Full Original Brief

This is the original scope document for the trading management system. Phase 1
(accounts/trades/allocations schema + CSV import) is being built first, but this
file gives the full picture of where the system is headed so decisions made now
don't box in later phases.

---

You're at the starting line with ~$550k in funded accounts (5 × $50k Lucid Flex,
2 × $150k Topstep) plus personal live accounts. The hardest constraint: profit
allocation and account separation must be bulletproof — no cross-account data
leaks, all calculations auditable and traceable.

This is a solo project, not a team build. It's for personal use right now (not a
multi-tenant SaaS) — one person operating and tracking their own accounts. It
needs to scale to 10+ accounts and $2M+ capital over time, co-built iteratively
with Claude Code rather than fully speced up front.

## Core Modules (full scope, built in phases — not all at once)

1. **Trading Journal & Operations** — daily log, CSV import from trading
   platforms, trade tagging, P&L per trade, alerts for risk deviations, meeting
   logs
2. **Dashboard & Analytics** — P&L by period (day/week/month/year), setup
   performance analysis, time-based patterns, real-time account status
3. **Account Management** — strict funded/personal separation, automated profit
   allocation, account history and status tracking, payouts
4. **Strategy Development & Testing** — systematic strategy builder, risk rules
   engine, position sizing logic, backtesting, validation before live deployment
5. **Portfolio Management** — separate stock portfolio tracking with
   quarterly/yearly/4-year/5-year returns, holdings allocation, integration with
   personal accounts
6. **Wellness & Decision Support** — mindfulness module, structured trade review
   space, emotional state tracking
7. **Data Architecture** — scalable multi-account database, CSV import pipeline
   with validation, historical audit trails, real-time sync

## Build sequence (why Phase 1 is scoped the way it is)

- **Phase 1 (this package):** account/trade/allocation schema + CSV import.
  Everything else reads from this, so it has to be right before anything else
  is built on top of it.
- **Phase 2:** trading journal UI, dashboard/analytics (read-only views over
  Phase 1 data), profit allocation made visible (manual payouts still fine).
- **Phase 3:** strategy engine + backtesting (depends on having clean trade
  history from Phase 1/2). Portfolio management can be built in parallel — it's
  a separate domain (personal stock accounts) and doesn't block or get blocked
  by the strategy engine.
- **Phase 4:** automated payouts, multi-account risk aggregation, wellness
  module. Wellness has no technical dependencies on anything else — it can slot
  in whenever, it's just not urgent.

## Non-negotiable architectural rule carried through every phase

No account balance is ever a stored, directly-mutated field. It is always
derived from `trades.pnl_net` (closed trades) + `allocations.amount`. This is
what makes account separation and audit trails bulletproof rather than
"probably fine" — the schema enforces it, not application discipline.

What I meant by "automated payouts" was narrower: automating the calculation of when you're eligible and what the split should be — the system watching your allocations ledger and trade history and telling you "you're eligible for a payout on Account X, here's the amount, here's the 90/10 split" — so you're not doing that math by hand before you go submit the manual request on Lucid's or Topstep's dashboard. The actual clicking-submit-on-their-site step stays manual and always will, since it requires their KYC flow.
