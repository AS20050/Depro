import os
import re
from urllib.parse import urlparse, unquote
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
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
    """Create new tables and migrate existing ones (non-destructive)."""
    async with engine.begin() as conn:
        from db.models import User, Deployment, AWSAccount, BillingThreshold  # noqa

        # 1. Create any tables that don't exist yet
        await conn.run_sync(Base.metadata.create_all)

        # 2. Safe column migrations — ADD COLUMN IF NOT EXISTS
        #    This handles cases where we added new columns to existing tables.
        migrations = [
            # Deployment table — columns added after initial creation
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS source_type VARCHAR(20)",
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS source_filename VARCHAR(255)",
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS repo_url TEXT",
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS file_path TEXT",
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS aws_service VARCHAR(50)",
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS aws_region VARCHAR(30) DEFAULT 'ap-south-1'",
            "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
            # User table — billing alert tracking
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_alerted_total DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_alert_sent_at TIMESTAMPTZ",
            # User table — AWS vault reference
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS aws_access_key_id VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS aws_default_region VARCHAR(30) DEFAULT 'ap-south-1'",
        ]
        for sql in migrations:
            await conn.execute(text(sql))

    print("✅ [DB] Tables created / migrated.")
