import os
import uuid
import httpx
import psycopg
from app.v11_governance import request_approval, decide_once
from app.reliability.dispatcher import dispatch_once

TOOL='servicenow.incident.create'
def test_commit_then_timeout_reconciles_without_duplicate(db_url,tenant,run_id):
    with psycopg.connect(db_url) as db:
        request_approval(db,tenant,run_id)
        decide_once(db,tenant,run_id,'approver',True,TOOL,
                    {'tool':TOOL,'account_id':'ACME','short_description':'Investigate customer risk'})
    result=dispatch_once(tenant,'timeout_after_commit')
    assert result['status']=='CONFIRMED'
    assert dispatch_once(tenant)['status']=='EMPTY'
    with psycopg.connect(os.environ['ADMIN_DATABASE_URL']) as db:
        assert db.execute('SELECT count(*) FROM sim_incidents_v2 WHERE tenant_id=%s AND idempotency_key=%s',(tenant,result['action_key'])).fetchone()[0]==1

def test_provider_rejects_different_payload_for_same_key(tenant):
    key='test-'+uuid.uuid4().hex
    base=os.environ['SIMULATOR_URL']
    with httpx.Client(timeout=5) as client:
        a=client.post(base+'/sim/incidents',headers={'Idempotency-Key':key},json={'tenant_id':tenant,'account_id':'ACME','summary':'First valid description'})
        b=client.post(base+'/sim/incidents',headers={'Idempotency-Key':key},json={'tenant_id':tenant,'account_id':'ACME','summary':'Different description'})
    assert a.status_code==200
    assert b.status_code==409


def test_precommit_outage_parks_manual_review(db_url,tenant,run_id):
    with psycopg.connect(db_url) as db:
        request_approval(db,tenant,run_id)
        decide_once(db,tenant,run_id,'approver',True,TOOL,
                    {'tool':TOOL,'account_id':'ACME','short_description':'Investigate customer risk'})
    result=dispatch_once(tenant,'before_commit')
    assert result['status']=='UNCERTAIN'
    assert result['requires_manual_reconciliation'] is True
    assert dispatch_once(tenant)['status']=='EMPTY'  # parked, not automatically resent
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id',%s,true)",(tenant,))
        assert db.execute('SELECT status FROM v11_outbox WHERE run_id=%s',(run_id,)).fetchone()[0]=='UNCERTAIN'
