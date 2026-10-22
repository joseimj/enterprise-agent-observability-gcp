"""REAL PostgreSQL + live simulator integration (Docker/CI only).

These tests run actual LangGraph/PostgresSaver, outbox transactions,
service worker, HTTP simulator and audit persistence. Never use live SaaS.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from app.v11_governance import decide_once, request_approval
from app.v1_audit import history
from app.v2_service import begin, decision, inspect
from app.reliability.governed_worker import dispatch_once
from app.v2_worker import claim

TOOL = 'servicenow.incident.create'


def _payload():
    return {'tool': TOOL, 'account_id': 'ACME',
            'short_description': 'Investigate critical customer risk'}


def _approve(db_url, tenant, run_id, approved=True):
    with psycopg.connect(db_url) as db:
        request_approval(db, tenant, run_id)
        decide_once(db, tenant, run_id, 'integration-approver', approved,
                    TOOL, _payload())


def _dispatch(tenant, fault='none'):
    return asyncio.run(dispatch_once(tenant, fault_mode=fault))


def _status(db_url, tenant, run_id):
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        status = db.execute(
            'SELECT status,attempts FROM v11_outbox WHERE tenant_id=%s AND run_id=%s',
            (tenant, run_id)).fetchone()
        events = history(db, tenant, run_id)
    return status, events


def test_real_langgraph_approval_outbox_timeout_and_audit(db_url, tenant, run_id, monkeypatch):
    monkeypatch.setenv('SERVICENOW_PROVIDER_MODE', 'simulator')
    with PostgresSaver.from_conn_string(os.environ['CHECKPOINT_DATABASE_URL']) as saver:
        saver.setup()
    monkeypatch.setenv('AUDIT_DATABASE_URL', db_url)
    started = begin(tenant, 'integration-operator', 'ACME', run_id)
    assert started['status'] == 'PENDING_APPROVAL'
    # begin() and decision() each construct a new graph and DB connection.
    assert decision(tenant, 'integration-approver', run_id, True)['graph'] == 'RESUMED'
    queued, before = _status(db_url, tenant, run_id)
    assert queued == ('PENDING', 0)
    assert [e['event_type'] for e in before] == [
        'V2_APPROVAL_REQUESTED', 'V2_DECISION_COMMITTED'
    ]
    completed = _dispatch(tenant, 'timeout_after_commit')
    assert completed['status'] == 'CONFIRMED'
    assert _dispatch(tenant)['status'] == 'EMPTY'
    after, events = _status(db_url, tenant, run_id)
    assert after == ('SUCCEEDED', 1)
    assert [e['event_type'] for e in events][-1] == 'PROVIDER_CONFIRMED'
    assert inspect(tenant, run_id)['outbox'][0]['status'] == 'SUCCEEDED'
    with psycopg.connect(os.environ['ADMIN_DATABASE_URL']) as db:
        count = db.execute('''SELECT count(*) FROM sim_incidents_v2
            WHERE tenant_id=%s AND idempotency_key=%s''',
            (tenant, completed['action_key'])).fetchone()[0]
    assert count == 1


def test_parallel_dispatch_one_external_effect(db_url, tenant, run_id, monkeypatch):
    monkeypatch.setenv('SERVICENOW_PROVIDER_MODE', 'simulator')
    _approve(db_url, tenant, run_id)
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: _dispatch(tenant), range(4)))
    assert [x['status'] for x in outcomes].count('CONFIRMED') == 1
    assert [x['status'] for x in outcomes].count('EMPTY') == 3
    final, events = _status(db_url, tenant, run_id)
    assert final == ('SUCCEEDED', 1)
    assert len([e for e in events if e['event_type'] == 'PROVIDER_CONFIRMED']) == 1


def test_reclaimed_lease_parks_without_second_post(db_url, tenant, run_id, monkeypatch):
    monkeypatch.setenv('SERVICENOW_PROVIDER_MODE', 'simulator')
    _approve(db_url, tenant, run_id)
    with psycopg.connect(db_url) as db:
        first = claim(db, tenant)
        assert first[-1] == 1
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        db.execute('''UPDATE v11_outbox SET leased_until = now() - interval '1 second'
            WHERE tenant_id=%s AND id=%s''', (tenant, first[0]))
    resumed = _dispatch(tenant)
    assert resumed['status'] == 'UNCERTAIN'
    final, events = _status(db_url, tenant, run_id)
    assert final == ('UNCERTAIN', 2)
    assert events[-1]['event_type'] == 'PROVIDER_OUTCOME_UNCERTAIN'
    with httpx.Client(timeout=5) as http:
        external = http.get(os.environ['SIMULATOR_URL'] + '/sim/incidents/by-key/' + first[4],
                            params={'tenant_id': tenant})
    assert external.status_code == 404
    assert _dispatch(tenant)['status'] == 'EMPTY'


def test_denied_action_is_never_enqueued(db_url, tenant, run_id):
    _approve(db_url, tenant, run_id, approved=False)
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        assert db.execute('''SELECT count(*) FROM v11_outbox WHERE tenant_id=%s
            AND run_id=%s''', (tenant, run_id)).fetchone()[0] == 0


def test_simulator_idempotency_is_scoped_to_tenant(tenant):
    key = 'sim-scope-' + uuid.uuid4().hex[:20]
    other = 'other-' + uuid.uuid4().hex[:10]
    url = os.environ['SIMULATOR_URL']
    with httpx.Client(timeout=10) as http:
        def create(scope):
            return http.post(url + '/sim/incidents', headers={'Idempotency-Key': key},
                             json={'tenant_id':scope, 'account_id':'ACME',
                                   'summary':'Same action identifier in separate tenant'})
        a = create(tenant)
        b = create(other)
        assert a.status_code == 200 and b.status_code == 200
        assert a.json()['number'] != b.json()['number']
        assert create(tenant).json()['number'] == a.json()['number']
        for scope, expected in ((tenant, a.json()), (other, b.json())):
            lookup = http.get(url + '/sim/incidents/by-key/' + key,
                              params={'tenant_id': scope})
            assert lookup.status_code == 200
            assert lookup.json()['number'] == expected['number']
        assert http.get(url + '/sim/incidents/by-key/' + key,
                        params={'tenant_id':'unrelated'}).status_code == 404


def test_runtime_role_is_not_superuser_and_rls_is_active(db_url, tenant, run_id):
    _approve(db_url, tenant, run_id)
    with psycopg.connect(db_url) as db:
        role = db.execute('''SELECT rolsuper,rolbypassrls FROM pg_roles
            WHERE rolname=current_user''').fetchone()
        assert role == (False, False)
        assert db.execute("SELECT row_security_active('v11_outbox'::regclass)").fetchone()[0]
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        assert db.execute('SELECT count(*) FROM v11_outbox').fetchone()[0] == 1
    with psycopg.connect(db_url) as db:
        db.execute("SELECT set_config('app.tenant_id', %s, true)", ('unrelated-tenant',))
        assert db.execute('SELECT count(*) FROM v11_outbox').fetchone()[0] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('''INSERT INTO v11_outbox(tenant_id,run_id,action_key,tool,payload)
                VALUES (%s,%s,%s,%s,%s::jsonb)''',
                (tenant, run_id, 'cross-tenant-' + uuid.uuid4().hex, TOOL, '{}'))


def test_transaction_local_tenant_does_not_leak_between_transactions(db_url, tenant, run_id):
    _approve(db_url, tenant, run_id)
    with psycopg.connect(db_url, autocommit=True) as db:
        with db.transaction():
            db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            assert db.execute('SELECT count(*) FROM v11_outbox').fetchone()[0] == 1
        with db.transaction():
            assert db.execute('SELECT count(*) FROM v11_outbox').fetchone()[0] == 0
