"""Mock-only outbox worker with fencing token to reject stale lease completions."""
import os
import psycopg
from opentelemetry import trace
from app.v1_audit import record

TRACER=trace.get_tracer('v2.outbox')

def claim(conn,tenant):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
    return conn.execute("""WITH candidate AS (
      SELECT id FROM v11_outbox WHERE tenant_id=%s AND
      (status='PENDING' OR (status='IN_PROGRESS' AND leased_until < now()))
      ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
      UPDATE v11_outbox SET status='IN_PROGRESS',attempts=attempts+1,
      leased_until=now()+interval '2 minutes' WHERE id IN (SELECT id FROM candidate)
      RETURNING id,run_id,tool,payload,action_key,attempts""",(tenant,)).fetchone()

def finish(conn,tenant,item,attempt):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
    return conn.execute("""UPDATE v11_outbox SET status='SUCCEEDED',completed_at=now(),leased_until=NULL
      WHERE tenant_id=%s AND id=%s AND status='IN_PROGRESS' AND attempts=%s
      AND leased_until > now() RETURNING run_id""",(tenant,item,attempt)).fetchone()

def run_once(tenant):
    # Legacy mock runners can falsely mark an outbox row complete. Prevent
    # accidental use in a non-lab deployment; use governed_worker instead.
    if not (os.getenv('DEPLOYMENT_ENV') == 'local' and
            os.getenv('ENABLE_LEGACY_MOCK_WORKER') == 'true'):
        raise PermissionError('Legacy mock completion worker disabled')
    # Worker tenant identity must come from trusted deployment config, never a request body.
    with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
        item=claim(db,tenant)
    if not item:return {'status':'EMPTY'}
    item_id,run_id,tool,payload,key,attempt=item
    with TRACER.start_as_current_span('outbox.mock_dispatch') as span:
        span.set_attribute('agent.run_id',str(run_id))
        span.set_attribute('tool.name',tool)
        if tool!='servicenow.incident.create':
            raise ValueError('Unrecognized tool; left for operator intervention')
        # No actual ServiceNow API call. An actual provider needs reconciliation.
        with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
            result=finish(db,tenant,item_id,attempt)
            if result:
                record(db,tenant,str(run_id),'V2_MOCK_ACTION_COMPLETED','v2-worker',
                       {'tool':tool,'action_key':key,'attempt':attempt})
        return {'status':'SIMULATED' if result else 'STALE_LEASE','action_key':key}

if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise SystemExit('Usage: python -m app.v2_worker TRUSTED_TENANT_ID')
    print(run_once(sys.argv[1]))
