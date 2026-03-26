"""Alembic environment — reads DATABASE_URL from environment / .env file."""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make backend/app importable so models can be referenced
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Alembic Config object (gives access to alembic.ini values)
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment variable if present
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# We use plain SQL migrations (no autogenerate from metadata needed for Phase 1)
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version",
        version_locations=os.path.join(os.path.dirname(__file__), "migrations"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connected to a live DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version",
            version_locations=os.path.join(os.path.dirname(__file__), "migrations"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
