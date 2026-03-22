import os
import re
from urllib.parse import urlparse, unquote
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/depro")


def _ensure_database_exists():
    """
    Auto-create the PostgreSQL database if it doesn't exist.
    Connects to the default 'postgres' DB to check/create the target DB.
    This runs once on startup so any new machine just needs PostgreSQL installed.
    """
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    # Parse the async URL to extract connection details
    # postgresql+asyncpg://user:pass@host:port/dbname
    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url)

    db_name = parsed.path.lstrip("/")
    user = parsed.username or "postgres"
    password = unquote(parsed.password) if parsed.password else ""
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432

    try:
        # Connect to the default 'postgres' database
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Check if our database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()

        if not exists:
            cur.execute(f'CREATE DATABASE "{db_name}"')
            print(f"🆕 [DB] Database '{db_name}' created automatically.")
        else:
            print(f"✅ [DB] Database '{db_name}' exists.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️  [DB] Could not auto-create database: {e}")
        print(f"    Make sure PostgreSQL is running on {host}:{port}")


# Auto-create DB on import (runs at startup before engine connects)
_ensure_database_exists()

engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        from db.models import User, Deployment, AWSAccount  # noqa
        await conn.run_sync(Base.metadata.create_all)
    print("✅ [DB] Tables created / verified.")
