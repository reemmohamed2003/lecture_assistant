"""Database session for M4.

Dev default is a local SQLite file. Set M4_DATABASE_URL to use the team's
Postgres. M1 owns the real database setup and migrations; this keeps us
independent until then.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import m4.quiz.models

from m4.profile.models import Base
import m4.quiz.models  # noqa: F401  (registers the quiz tables on Base)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(os.getenv("M4_DATABASE_URL", "sqlite:///m4_dev.db"))
        Base.metadata.create_all(_engine)
    return _engine


def get_session():
    with Session(get_engine()) as session:
        yield session