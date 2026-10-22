"""Worker state-machine tests using fake DB connections and fake provider.

These verify retry policy and fencing behavior, not PostgreSQL concurrency.
"""
import asyncio
import importlib
import sys
import types
from uuid import uuid4

import pytest
from app.connectors.servicenow import ServiceNowUncertainWrite, ServiceNowContractError

TOOL = 'servicenow.incident.create'


class FakeCursor:
    def __init__(self, value):
        self.value = value
    def fetchone(self):
        return self.value


class FakeDb:
    def __init__(self):
        self.commands = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params):
        self.commands.append((sql, params))
        return FakeCursor(('row',))


class Provider:
    def __init__(self, *, created='0123456789abcdef0123456789abcdef', found=None, error=None):
        self.created, self.found, self.error = created, found, error
        self.post_calls = 0
        self.lookup_calls = 0
    async def create_once(self, action):
        self.post_calls += 1
        if self.error: raise self.error
        return self.created
    async def lookup_by_key(self, key, tenant):
        self.lookup_calls += 1
        return self.found


@pytest.fixture
def harness(monkeypatch):
    # The local runner does not have psycopg installed. An import shim enables
    # deterministic unit tests; real SQL semantics are separately tested in CI.
    fake_psycopg = types.ModuleType('psycopg')
    databases = []
    def connect(dsn):
        db=FakeDb()
        databases.append(db)
        return db
    fake_psycopg.connect=connect
    monkeypatch.setitem(sys.modules, 'psycopg', fake_psycopg)
    # Import modules once with the test-only psycopg shim.
    for name in ('app.v1_audit', 'app.v2_worker', 'app.reliability.governed_worker'):
        sys.modules.pop(name, None)
    mod=importlib.import_module('app.reliability.governed_worker')
    runid=str(uuid4())
    attempt_holder={'count': 1}
    events=[]
    def claim(_db, tenant):
        return ('item', runid, TOOL,
                {'tool':TOOL, 'account_id':'ACME', 'short_description':'Critical risk'},
                'action-000001', attempt_holder['count'])
    monkeypatch.setattr(mod,'claim',claim)
    monkeypatch.setattr(mod,'finish',lambda *_: ('row',))
    monkeypatch.setattr(mod,'record',lambda *args: events.append(args))
    monkeypatch.setenv('AUDIT_DATABASE_URL','fake://db')
    yield mod, attempt_holder, databases, events
    for name in ('app.v1_audit', 'app.v2_worker', 'app.reliability.governed_worker'):
        sys.modules.pop(name, None)


def execute(worker, provider):
    return asyncio.run(worker.dispatch_once('business_a', provider))


def test_normal_creation_confirms(harness):
    w, attempts, databases, events=harness
    p=Provider()
    result=execute(w,p)
    assert result['status']=='CONFIRMED'
    assert p.post_calls==1 and p.lookup_calls==0
    assert events[0][3]=='PROVIDER_CONFIRMED'


def test_uncertain_write_unconfirmed_lookup_parks(harness):
    w, attempts, databases, events=harness
    p=Provider(error=ServiceNowUncertainWrite('response lost'))
    result=execute(w,p)
    assert result['status']=='UNCERTAIN'
    assert p.post_calls==1 and p.lookup_calls==1
    assert events[0][3]=='PROVIDER_OUTCOME_UNCERTAIN'
    assert any("status='UNCERTAIN'" in sql for db in databases for sql, _ in db.commands)


def test_uncertain_write_confirmed_by_lookup(harness):
    w, attempts, databases, events=harness
    p=Provider(error=ServiceNowUncertainWrite('response lost'), found='real-sysid')
    result=execute(w,p)
    assert result['status']=='CONFIRMED'
    assert result['provider_id']=='real-sysid'
    assert p.post_calls==1 and p.lookup_calls==1


def test_conflict_cannot_be_cleared_by_lookup(harness):
    w, attempts, databases, events=harness
    p=Provider(error=ServiceNowContractError('key reused with different payload'), found='existing-record')
    result=execute(w,p)
    assert result['status']=='UNCERTAIN'
    assert p.post_calls==1 and p.lookup_calls==0
    assert events[0][-1]['reason']=='provider_contract_conflict'


def test_reclaimed_lease_confirmed_without_second_post(harness):
    w, attempts, databases, events=harness
    attempts['count']=2
    p=Provider(found='existing-record')
    result=execute(w,p)
    assert result['status']=='CONFIRMED'
    assert p.post_calls==0 and p.lookup_calls==1


def test_reclaimed_lease_missing_lookup_parks_without_post(harness):
    w, attempts, databases, events=harness
    attempts['count']=3
    p=Provider(found=None)
    result=execute(w,p)
    assert result['status']=='UNCERTAIN'
    assert p.post_calls==0 and p.lookup_calls==1


def test_live_mode_requires_explicit_certification(harness, monkeypatch):
    w, attempts, databases, events=harness
    monkeypatch.setenv('SERVICENOW_PROVIDER_MODE','scripted')
    monkeypatch.delenv('ENABLE_SERVICENOW_REAL_WRITES', raising=False)
    monkeypatch.delenv('SERVICENOW_DEDUP_CERTIFIED', raising=False)
    with pytest.raises(PermissionError):
        asyncio.run(w.dispatch_once('business_a'))
    assert not databases  # configuration rejected BEFORE claiming work
