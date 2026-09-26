"""DB engine/session. Defaults to a local SQLite file so the API and
tests run without Docker; set DATABASE_URL (see .env.example) to point
at the real Postgres service for anything beyond local dev."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

def normalize_database_url(url: str) -> str:
    """Name the psycopg2 driver explicitly. Hosts hand out plain
    `postgres://` / `postgresql://` URLs, and SQLAlchemy 2.1 reads those as
    the newer psycopg 3 driver, which this project does not install."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix) :]
    return url


DATABASE_URL = normalize_database_url(os.environ.get("DATABASE_URL", "sqlite:///./cip.db"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pool_pre_ping: hosted Postgres (Neon) drops idle connections; replace them
# transparently instead of failing the first request after a quiet period.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
