# FRONTEND_SETUP.md — Phase 1

This is its own repo (`trading-frontend` or whatever you name it), completely
separate from the backend. Read `CONTEXT.md` first for the full application
picture.

## Stack
React + Vite, deployed free on Vercel. See `TECH_STACK.md` for reasoning.

## Important: there is no frontend work in Phase 1

Phase 1 is schema + CSV import only, on the backend. There are no API
endpoints to call yet, so there is nothing real for a frontend to display.
Building UI now means building it against a mock or nothing, then redoing it
once real endpoints exist in Phase 2 — that's wasted work.

**What to actually do in this repo right now:**

1. Scaffold the project so it's ready to go the moment Phase 2 backend
   endpoints exist:
   ```
   npm create vite@latest . -- --template react
   npm install
   ```

2. Create `.env.example`:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```
   (Update to the real Render URL once the backend is deployed.)

3. Set up a single shared API client file (e.g. `src/api/client.js`) that
   reads `VITE_API_BASE_URL` — every future fetch call goes through this one
   place, so switching from local backend to deployed backend is a one-line
   env change, not a find-and-replace across the codebase.

4. Deploy this empty-but-scaffolded shell to Vercel now (connect the GitHub
   repo, default Vite build settings) so the deploy pipeline is proven working
   before there's real UI riding on it.

## Phase 2 (don't build yet — for context only)

Once the backend exposes real endpoints (`GET /accounts/:id/balance`,
`GET /accounts/:id/trades`, etc.), the frontend starts with read-only views:
account list, per-account balance, trade list. No forms/mutations needed yet
since Phase 1/2 data entry is via CSV import + direct DB, not a UI.

## Definition of done for frontend Phase 1

- [ ] Vite React project scaffolded and running locally (`npm run dev`)
- [ ] `VITE_API_BASE_URL` env pattern in place, no hardcoded URLs anywhere
- [ ] Deployed to Vercel successfully (even showing just a placeholder page)
- [ ] Confirmed you can update `VITE_API_BASE_URL` in Vercel's dashboard and
      redeploy without touching code
