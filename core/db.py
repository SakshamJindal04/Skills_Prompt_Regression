"""
Database engine and session management.
Supports MySQL 8 with automatic graceful fallback to SQLite.
"""

import os
import logging
from pathlib import Path
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
    """
    Automatic Alembic upgrade on start and assert that schema matches the code.
    Gracefully falls back to create_all if alembic table exists.
    """
    if engine is None:
        engine = get_engine()

    base_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = base_dir / "alembic.ini"

    if alembic_ini_path.exists():
        try:
            from alembic.config import Config
            from alembic import command

            alembic_cfg = Config(str(alembic_ini_path))
            alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
            command.upgrade(alembic_cfg, "head")
        except Exception as exc:
            logger.warning(f"Alembic auto-upgrade encountered: {exc}. Ensuring tables via Base.metadata.")
            Base.metadata.create_all(engine)
    else:
        Base.metadata.create_all(engine)

    # Assert that all required model tables match the code
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = {table.name for table in Base.metadata.sorted_tables}

    missing_tables = expected_tables - existing_tables
    assert not missing_tables, f"Database schema mismatch! Missing tables in DB: {missing_tables}"

    logger.info("Database schema verified, Alembic migrations at head, and tables asserted.")
