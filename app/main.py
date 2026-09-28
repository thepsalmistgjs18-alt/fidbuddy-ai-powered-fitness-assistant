"""
main.py
FastAPI entry point for FitBuddy - AI Fitness Plan Generator.

Run with:
    uvicorn app.main:app --reload

Then visit:
    http://127.0.0.1:8000        -> the app
    http://127.0.0.1:8000/docs   -> interactive API docs
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import application modules relative to this package.
from .init_db import init_db
from .routes import router

app = FastAPI(
    title="FitBuddy",
    description="AI Fitness Plan Generator",
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return the application's liveness status."""
    return {"status": "ok"}

# call the database initialization function
init_db()

# Serve static assets properly
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# All page + API routes
app.include_router(router)