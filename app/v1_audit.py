"""Durable, tenant-keyed events; use separate low-privilege database role in production."""
import os
import json
from contextlib import contextmanager
from datetime import datetime, timezone
import psycopg

@contextmanager
def connect():
    dsn = os.getenv('AUDIT_DATABASE_URL')
    if not dsn: raise RuntimeError('AUDIT_DATABASE_URL missing')
    with psycopg.connect(dsn) as conn:
        yield conn

def record(conn, tenant, run_id, kind, actor, payload):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
    conn.execute("""INSERT INTO v1_audit_events(tenant_id,run_id,event_type,actor_id,payload)
                    VALUES (%s,%s,%s,%s,%s::jsonb)""",
                 (tenant,run_id,kind,actor,json.dumps(payload)))

def history(conn,tenant,run_id):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)",(tenant,))
    return [dict(id=str(r[0]),event_type=r[1],actor_id=r[2],payload=r[3],created_at=r[4].isoformat())
            for r in conn.execute("""SELECT id,event_type,actor_id,payload,created_at
                FROM v1_audit_events WHERE tenant_id=%s AND run_id=%s ORDER BY created_at,id""",(tenant,run_id))]
