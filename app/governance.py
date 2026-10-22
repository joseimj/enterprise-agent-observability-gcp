"""Durable action audit and human approval gateway. No credentials or payload bodies are stored."""
import hashlib, json, os, uuid
from datetime import datetime, timezone
from typing import Literal
import psycopg
from psycopg.rows import dict_row
from opentelemetry import trace

DDL = """
CREATE TABLE IF NOT EXISTS audit_events (
  event_id UUID PRIMARY KEY, run_id UUID NOT NULL, tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL, event_type TEXT NOT NULL, tool_name TEXT,
  action_id UUID, status TEXT NOT NULL, trace_id TEXT,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_events(tenant_id, run_id, created_at);
CREATE TABLE IF NOT EXISTS action_requests (
  action_id UUID PRIMARY KEY, run_id UUID NOT NULL, tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL, tool_name TEXT NOT NULL,
  arguments JSONB NOT NULL, arguments_hash TEXT NOT NULL,
  idempotency_key TEXT NOT NULL, status TEXT NOT NULL,
  approved_by TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, idempotency_key)
);
"""
def _demo_dsn():
    dsn = os.environ.get('AUDIT_DATABASE_URL')
    if not dsn:
        raise RuntimeError('AUDIT_DATABASE_URL required; no default superuser credentials')
    return dsn

def connect(): return psycopg.connect(_demo_dsn(), row_factory=dict_row)

def init_db():
    with connect() as conn:
        for statement in DDL.strip().split(';'):
            if statement.strip(): conn.execute(statement)

def emit(conn, *, run_id, tenant_id, actor_id, event_type, status, tool_name=None, action_id=None, details=None):
    span=trace.get_current_span().get_span_context()
    trace_id=f'{span.trace_id:032x}' if span.is_valid else None
    event_id=str(uuid.uuid4())
    conn.execute('INSERT INTO audit_events (event_id,run_id,tenant_id,actor_id,event_type,tool_name,action_id,status,trace_id,details) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
       (event_id,run_id,tenant_id,actor_id,event_type,tool_name,action_id,status,trace_id,json.dumps(details or {})))
    return event_id

ALLOWED_TOOLS={'jira.create_followup', 'servicenow.create_incident'}

def request_action(*,run_id,tenant_id,actor_id,tool_name,arguments,idempotency_key):
    from app.action_policy import ActionPolicy
    arguments = ActionPolicy.validate(tool_name, arguments)
    digest=hashlib.sha256(json.dumps(arguments,sort_keys=True).encode()).hexdigest()
    with connect() as conn:
        existing=conn.execute('SELECT * FROM action_requests WHERE tenant_id=%s AND idempotency_key=%s FOR UPDATE',(tenant_id,idempotency_key)).fetchone()
        if existing:
            if existing['arguments_hash']!=digest or existing['tool_name']!=tool_name: raise ValueError('Idempotency key conflict')
            return existing
        action_id=str(uuid.uuid4())
        conn.execute('INSERT INTO action_requests (action_id,run_id,tenant_id,actor_id,tool_name,arguments,arguments_hash,idempotency_key,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
          (action_id,run_id,tenant_id,actor_id,tool_name,json.dumps(arguments),digest,idempotency_key,'PENDING'))
        emit(conn,run_id=run_id,tenant_id=tenant_id,actor_id=actor_id,event_type='ACTION_REQUESTED',status='PENDING',tool_name=tool_name,action_id=action_id,details={'arguments_hash':digest})
        return conn.execute('SELECT * FROM action_requests WHERE action_id=%s',(action_id,)).fetchone()

def decide(*,action_id,tenant_id,approver_id,approve):
    with connect() as conn:
        row=conn.execute('SELECT * FROM action_requests WHERE action_id=%s AND tenant_id=%s FOR UPDATE',(action_id,tenant_id)).fetchone()
        if row is None: return None
        if row['status']!='PENDING': raise ValueError('Action already decided')
        if row['actor_id']==approver_id: raise ValueError('Self-approval forbidden')
        status='APPROVED' if approve else 'DENIED'
        conn.execute('UPDATE action_requests SET status=%s,approved_by=%s,updated_at=now() WHERE action_id=%s',(status,approver_id,action_id))
        emit(conn,run_id=row['run_id'],tenant_id=tenant_id,actor_id=approver_id,event_type='ACTION_DECISION',status=status,tool_name=row['tool_name'],action_id=action_id)
        return status

def execute(*,action_id,tenant_id,actor_id):
    """Mock execution only. Production connectors must implement reconciliation and outbox delivery."""
    with connect() as conn:
        row=conn.execute('SELECT * FROM action_requests WHERE action_id=%s AND tenant_id=%s FOR UPDATE',(action_id,tenant_id)).fetchone()
        if row is None: return None
        if row['status']=='EXECUTED': return 'EXECUTED'
        if row['status']!='APPROVED': raise ValueError('Action is not approved')
        # In this demo, no external write occurs. Only record the simulated outcome.
        conn.execute('UPDATE action_requests SET status=%s,updated_at=now() WHERE action_id=%s',('EXECUTED',action_id))
        emit(conn,run_id=row['run_id'],tenant_id=tenant_id,actor_id=actor_id,event_type='ACTION_EXECUTED_MOCK',status='EXECUTED',tool_name=row['tool_name'],action_id=action_id)
        return 'EXECUTED'

def timeline(*,run_id,tenant_id):
    with connect() as conn:
        return conn.execute('SELECT event_id,run_id,tenant_id,actor_id,event_type,tool_name,action_id,status,trace_id,details,created_at FROM audit_events WHERE tenant_id=%s AND run_id=%s ORDER BY created_at,event_id',(tenant_id,run_id)).fetchall()


def get_action(*,action_id,tenant_id):
    with connect() as conn:
        return conn.execute('SELECT action_id,run_id,tenant_id,actor_id,tool_name,status,approved_by,created_at,updated_at FROM action_requests WHERE action_id=%s AND tenant_id=%s',(action_id,tenant_id)).fetchone()

def list_actions(*,run_id,tenant_id):
    with connect() as conn:
        return conn.execute('SELECT action_id,run_id,tool_name,status,approved_by,created_at,updated_at FROM action_requests WHERE run_id=%s AND tenant_id=%s ORDER BY created_at,action_id',(run_id,tenant_id)).fetchall()
