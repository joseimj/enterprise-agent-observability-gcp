"""Transactional, one-time approvals and an outbox for mock external actions."""
import json
from uuid import UUID

ALLOWED_TOOLS = {'servicenow.incident.create'}

def action_key(run_id: str, tool: str) -> str:
    UUID(run_id)
    if tool not in ALLOWED_TOOLS:
        raise ValueError('Tool not allowlisted')
    return f'{run_id}:{tool}:v1'

def request_approval(conn, tenant, run_id):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
    conn.execute('INSERT INTO v11_approvals(tenant_id,run_id) VALUES (%s,%s) ON CONFLICT DO NOTHING', (tenant,run_id))

def decide_once(conn, tenant, run_id, approver, approved, tool, payload):
    """Atomically consume approval and enqueue the approved action in one transaction.

    Caller commits once; rollback on any exception. Never invoke external APIs here.
    """
    key = action_key(run_id,tool)
    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
    status = 'APPROVED' if approved else 'DENIED'
    row=conn.execute("""UPDATE v11_approvals SET status=%s, decided_by=%s, decided_at=now()
       WHERE tenant_id=%s AND run_id=%s AND status='PENDING' RETURNING status""",
       (status,approver,tenant,run_id)).fetchone()
    if row is None:
        raise ValueError('Approval missing or already consumed')
    if approved:
        conn.execute("""INSERT INTO v11_outbox(tenant_id,run_id,action_key,tool,payload)
           VALUES (%s,%s,%s,%s,%s::jsonb) ON CONFLICT (tenant_id,action_key) DO NOTHING""",
           (tenant,run_id,key,tool,json.dumps(payload)))
    return status

def claim_next(conn, tenant):
    """Worker must use tenant-scoped DB identity; claims are concurrency-safe."""
    conn.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
    return conn.execute("""WITH candidate AS (
       SELECT id FROM v11_outbox WHERE tenant_id=%s AND
       (status='PENDING' OR (status='IN_PROGRESS' AND leased_until < now()))
       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
       UPDATE v11_outbox SET status='IN_PROGRESS', attempts=attempts+1,
       leased_until=now()+interval '2 minutes' WHERE id IN (SELECT id FROM candidate)
       RETURNING id,run_id,tool,payload,action_key,attempts""",(tenant,)).fetchone()

def complete(conn, tenant, item_id):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
    return conn.execute("""UPDATE v11_outbox SET status='SUCCEEDED',completed_at=now(),leased_until=NULL
      WHERE tenant_id=%s AND id=%s AND status='IN_PROGRESS' RETURNING id""",(tenant,item_id)).fetchone()
