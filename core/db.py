"""
Database engine and session management.
Supports MySQL 8 with automatic graceful fallback to SQLite.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from core.models import Base

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MYSQL_URL = "mysql+pymysql://regression_user:regression_pass@localhost:3306/regression_db"
DEFAULT_SQLITE_URL = "sqlite:///regression_manager.db"

_engine = None
_SessionFactory = None
_active_db_type = "unknown"


def get_db_url() -> str:
    """Return database URL from environment or default to MySQL."""
    return os.getenv("DB_URL", DEFAULT_MYSQL_URL).strip()


def get_active_db_type() -> str:
    """Return whether currently connected to mysql or sqlite."""
    global _active_db_type
    if _engine is None:
        get_engine()
    return _active_db_type


def reset_engine():
    """Reset cached engine and session factory (primarily for testing)."""
    global _engine, _SessionFactory, _active_db_type
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
    _active_db_type = "unknown"


def get_engine():
    """Create or return existing SQLAlchemy engine with fallback support."""
    global _engine, _SessionFactory, _active_db_type
    if _engine is not None:
        return _engine

    db_url = get_db_url()

    # Attempt connecting with configured DB_URL
    try:
        if db_url.startswith("sqlite"):
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                echo=False,
            )
            _active_db_type = "sqlite"
        else:
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                echo=False,
            )
            _active_db_type = "mysql"
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _engine = engine
        logger.info(f"Database connected successfully to {db_url} (type: {_active_db_type})")
    except (OperationalError, Exception) as exc:
        if not db_url.startswith("sqlite"):
            logger.warning(
                f"Failed to connect to primary DB ({db_url}): {exc}. "
                f"Falling back to local SQLite at {DEFAULT_SQLITE_URL}."
            )
            _engine = create_engine(
                DEFAULT_SQLITE_URL,
                connect_args={"check_same_thread": False},
                echo=False,
            )
            _active_db_type = "sqlite"
        else:
            raise exc

    _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory():
    """Return session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        get_engine()
    return _SessionFactory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine=None):
    """Create all tables in the database."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN prev_hash VARCHAR(64) NULL"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN entry_hash VARCHAR(64) NULL"))
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass
    logger.info("Database schema verified and tables initialized.")
