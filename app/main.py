from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    accounts,
    aggregate_risk,
    analytics,
    csv_imports,
    dashboard,
    investments,
    journal,
    payouts,
    portfolio,
    quotes,
    risk,
    strategies,
    trades,
    wellness,
)

app = FastAPI(title="Trading Management API")

# Vite's default dev ports. Add the deployed frontend URL here once it exists.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(portfolio.router)
app.include_router(journal.router)
app.include_router(trades.router)
app.include_router(csv_imports.router)
app.include_router(risk.router)
app.include_router(analytics.router)
app.include_router(dashboard.router)
app.include_router(strategies.router)
app.include_router(investments.router)
app.include_router(payouts.router)
app.include_router(aggregate_risk.router)
app.include_router(wellness.router)
app.include_router(quotes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
