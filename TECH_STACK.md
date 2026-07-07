# Tech Stack — Phase 1 (Solo, Personal Use, Free Hosting)

Context: one person (you), personal use right now, two separate codebases
(backend / frontend), free hosting until this proves itself out.

## Recommendation

| Layer      | Choice                          | Why |
|------------|----------------------------------|-----|
| Database   | **Postgres via Neon**            | Real Postgres (needed for the UNIQUE constraints, triggers, and views in Phase 1) with a generous free tier and no forced sleep/expiry. |
| Backend    | **Python + FastAPI**             | The CSV import script already uses Python/psycopg2 — no reason to introduce a second language. FastAPI is lightweight, typed, and fast to iterate on with Claude Code. |
| Frontend   | **React + Vite**                 | Standard, fast dev loop, huge ecosystem, easiest to deploy free. |
| Backend hosting  | **Render (free web service)** | Free tier runs a real container; the trade-off is it sleeps after ~15 min idle and takes ~30–50s to wake. Fine for personal use, not fine if you need instant access at all hours — worth knowing. |
| Frontend hosting | **Vercel**                    | Best free tier for React/Vite specifically, instant deploys from git push, no sleep. |

### Why not the alternatives you mentioned
- **Laravel/PHP**: nothing here needs PHP's strengths, and it'd be a second
  language alongside the Python import script for no real benefit. Skip it
  unless you have a personal reason to prefer it.
- **Node/JS backend**: viable, but you'd lose the psycopg2-based import script
  already written and tested in Phase 1, and you'd be maintaining CSV
  parsing/validation logic in JS instead of Python's stronger data-handling
  ecosystem (this matters more once backtesting/analytics show up in Phase 3).

## Free hosting reality check

- Render's free tier sleeping is the main friction point. If that becomes
  annoying, the honest paid step-up is ~$7/mo for an always-on Render instance
  — worth knowing now, not a surprise later.
- Neon's free tier is generous enough for personal multi-account trade history
  for a long time; you will not need to pay for the database soon.
- Nothing here locks you in — Postgres is Postgres, FastAPI is a normal REST
  API, React is React. If you outgrow free hosting, moving off it later is a
  hosting change, not a rewrite.

## What this means for repo structure

Two separate git repos, as requested:

```
trading-backend/
  migrations/
  app/            <- FastAPI app code goes here in Phase 2
  scripts/
    import_csv.py
    requirements.txt
  .env.example
  README.md       <- see BACKEND_SETUP.md

trading-frontend/
  (created via `npm create vite@latest`)
  .env.example
  README.md       <- see FRONTEND_SETUP.md
```

They talk to each other over HTTP only — the frontend never touches the
database directly. That's the boundary that keeps two codebases actually
independent instead of secretly coupled.
