"""Tenant-scoped transactions; never accept tenant ID from unverified caller headers."""
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

@contextmanager
def tenant_session(engine, tenant_id: str):
    if not tenant_id or len(tenant_id) > 128:
        raise ValueError("Invalid verified tenant identity")
    with Session(engine) as session:
        with session.begin():
            # SET LOCAL is transaction scoped, avoiding connection pool tenant leaks.
            session.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id":tenant_id})
            yield session

def make_engine(url: str):
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
