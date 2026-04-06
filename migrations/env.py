"""
Alembic migration environment.

This file is loaded by Alembic when running migrations.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import the application's models and base
from protein_annotation_toolkit.config import get_settings
from protein_annotation_toolkit.db.base import Base

# Import all models so Alembic can detect them
from protein_annotation_toolkit.db.models import (  # noqa: F401
    BlastHit,
    BlastSearch,
    GOTerm,
    IngestionLog,
    KEGGPathway,
    Organism,
    PDBCrossref,
    Protein,
    ProteinGOTerm,
    ProteinKEGGPathway,
)

# Alembic Config object provides access to the .ini file
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from application settings
settings = get_settings()
# Convert async URL to sync URL for Alembic
database_url = str(settings.database_url).replace("+psycopg", "")
config.set_main_option("sqlalchemy.url", database_url)

# Set target metadata for autogenerate
# This tells Alembic what the schema should look like
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect column type changes
        compare_server_default=True,  # Detect default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we create an Engine and associate a connection with the context.
    """
    # Create engine from config
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes
            compare_server_default=True,  # Detect default value changes
        )

        with context.begin_transaction():
            context.run_migrations()


# Determine whether to run in offline or online mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
