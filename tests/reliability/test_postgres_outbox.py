from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from app.v11_governance import request_approval, decide_once
from app.v2_worker import claim, finish
from app.v1_audit import record,history

TOOL='servicenow.incident.create'
def payload():return {'tool':TOOL,'account_id':'ACME','short_description':'Investigate customer risk'}
def seed(dsn,tenant,run):
    with psycopg.connect(dsn) as db:
        request_approval(db,tenant,run)
        record(db,tenant,run,'APPROVAL_REQUESTED','test',{})

def test_one_time_approval_and_atomic_outbox(db_url,tenant,run_id):
    seed(db_url,tenant,run_id)
    def approve(_):
        try:
            with psycopg.connect(db_url) as db:
                decide_once(db,tenant,run_id,'approver',True,TOOL,payload())
                record(db,tenant,run_id,'APPROVED','approver',{})
            return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=4) as pool: outcomes=list(pool.map(approve,range(4)))
    assert outcomes.count(True)==1
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id',%s,true)",(tenant,))
        assert db.execute('SELECT count(*) FROM v11_outbox WHERE run_id=%s',(run_id,)).fetchone()[0]==1
        assert len(history(db,tenant,run_id))==2

def test_tenant_rls_and_scope_does_not_leak(db_url,tenant,run_id):
    seed(db_url,tenant,run_id)
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id',%s,true)",(tenant,))
        assert db.execute('SELECT count(*) FROM v11_approvals').fetchone()[0]==1
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id',%s,true)",('another-tenant',))
        assert db.execute('SELECT count(*) FROM v11_approvals WHERE run_id=%s',(run_id,)).fetchone()[0]==0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('INSERT INTO v11_approvals(tenant_id,run_id) VALUES (%s,%s)',(tenant,run_id))

def test_concurrent_worker_claims_once(db_url,tenant,run_id):
    seed(db_url,tenant,run_id)
    with psycopg.connect(db_url) as db:decide_once(db,tenant,run_id,'approver',True,TOOL,payload())
    def pick(_):
        with psycopg.connect(db_url) as db:return claim(db,tenant)
    with ThreadPoolExecutor(max_workers=3) as pool:claims=list(pool.map(pick,range(3)))
    assert sum(item is not None for item in claims)==1
    selected=next(i for i in claims if i is not None)
    with psycopg.connect(db_url) as db:
        assert finish(db,tenant,selected[0],selected[-1])
    with psycopg.connect(db_url) as db:assert finish(db,tenant,selected[0],selected[-1]) is None

def test_outbox_persists_when_application_connection_closes(db_url,tenant,run_id):
    seed(db_url,tenant,run_id)
    with psycopg.connect(db_url) as db:decide_once(db,tenant,run_id,'approver',True,TOOL,payload())
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id',%s,true)",(tenant,))
        assert db.execute('SELECT status FROM v11_outbox WHERE run_id=%s',(run_id,)).fetchone()[0]=='PENDING'
