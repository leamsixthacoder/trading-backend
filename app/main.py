from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import accounts, portfolio

app = FastAPI(title="Trading Management API")

# Vite's default dev ports. Add the deployed frontend URL here once it exists.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(portfolio.router)


@app.get("/health")
def health():
    return {"status": "ok"}
