import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from app.persistence.models import Base
config = context.config
target_metadata = Base.metadata

def run_migrations_online():
    url = os.environ["AUDIT_DATABASE_URL"]
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True, version_table_schema="public")
        with context.begin_transaction(): context.run_migrations()
    engine.dispose()

run_migrations_online()
