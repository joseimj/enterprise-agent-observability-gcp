from pathlib import Path
from app.persistence.models import Base
from app.persistence.tenant import tenant_session

def test_all_models_have_tenant_column():
    for table in Base.metadata.tables.values():
        assert "tenant_id" in table.c, table.name

def test_migration_contains_rls_and_force():
    script = Path("migrations/versions/0001_tenant_schemas.py").read_text()
    assert "FORCE ROW LEVEL SECURITY" in script
    assert "WITH CHECK" in script

def test_scoped_transaction_sets_tenant_locally():
    import inspect
    src = inspect.getsource(tenant_session)
    assert "set_config('app.tenant_id', :tenant_id, true)" in src
    assert "session.begin()" in src

def test_private_networking_config():
    cfg = Path("infrastructure/azure/postgres.tf").read_text()
    assert 'public_network_access_enabled = false' in cfg
    assert 'delegated_subnet_id' in cfg
    assert 'prevent_destroy = true' in cfg
