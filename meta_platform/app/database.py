"""Database configuration for the FastAPI-based meta platform."""
from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Expect PostgreSQL; fall back to a sane local default for dev.
DATABASE_URL = os.getenv(
    "META_PLATFORM_DATABASE_URL",
    "postgresql+psycopg://meta_platform:meta_platform@localhost:5432/meta_platform",
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
