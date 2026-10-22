"""One-shot lab worker: simulates ServiceNow writes; NEVER calls external APIs."""
import os
import psycopg
from app.v11_governance import claim_next, complete

def run_once(tenant):
    # Legacy mock runners can falsely mark an outbox row complete. Prevent
    # accidental use in a non-lab deployment; use governed_worker instead.
    if not (os.getenv('DEPLOYMENT_ENV') == 'local' and
            os.getenv('ENABLE_LEGACY_MOCK_WORKER') == 'true'):
        raise PermissionError('Legacy mock completion worker disabled')
    with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as conn:
        item=claim_next(conn,tenant)
    if item is None: return {'status':'EMPTY'}
    item_id,run_id,tool,payload,key,attempts=item
    # This is a MOCK. A real connector needs provider-side idempotency/reconciliation.
    with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as conn:
        complete(conn,tenant,item_id)
    return {'status':'SIMULATED','action_key':key,'attempts':attempts}

if __name__=='__main__':
    import sys
    if len(sys.argv)!=2: raise SystemExit('Usage: python -m scripts.v11_worker TENANT_ID')
    print(run_once(sys.argv[1]))
