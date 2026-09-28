"""Application startup hook for database initialization."""

from .database import init_db as initialize_database


def init_db() -> None:
    initialize_database()
