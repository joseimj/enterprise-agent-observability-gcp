"""Adversarial contract regressions — no ServiceNow credentials required."""
import asyncio
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from app.connectors.servicenow import ServiceNowContractError, ServiceNowUncertainWrite
from app.connectors.servicenow_scripted import ServiceNowScriptedProvider
from app.connectors.governed_servicenow import ProviderAction
from app.v1_identity import verify_token

SYSID = 'abcdef0123456789abcdef0123456789'
KEY = 'action-00001'
TENANT = 'business_a'
ACTION = ProviderAction(KEY, TENANT, 'Critical customer risk', 'Operational issues found')
BASE = 'https://dev123.service-now.com'


def run(coroutine):
    return asyncio.run(coroutine)


def call(handler, lookup=False):
    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            p = ServiceNowScriptedProvider(BASE, lambda: 'fake', client, enabled=True)
            if lookup:
                return await p.lookup_by_key(KEY, TENANT)
            return await p.create_once(ACTION)
    return run(invoke())


def reply(**overrides):
    value = {'sys_id':SYSID, 'tenant_id':TENANT, 'action_key':KEY, **overrides}
    return httpx.Response(201, json={'result':value})


def test_correlated_post_is_confirmed():
    assert call(lambda _:reply()) == SYSID


@pytest.mark.parametrize('body', [
    {'result':{}}, {'result':None}, {'result':'not-a-dict'},
    {'result':{'sys_id': SYSID}}, {'result':{'sys_id': SYSID, 'tenant_id':TENANT}},
])
def test_incomplete_post_ack_is_uncertain(body):
    with pytest.raises(ServiceNowUncertainWrite):
        call(lambda _:httpx.Response(201,json=body))



@pytest.mark.parametrize('change', [
    {'tenant_id':'business_b'}, {'action_key':'action-WRONG'},
    {'sys_id':'not-an-id'}, {'sys_id':None},
])
def test_wrong_post_correlation_is_uncertain(change):
    with pytest.raises(ServiceNowUncertainWrite):
        call(lambda _:reply(**change))


@pytest.mark.parametrize('change', [
    {'tenant_id':'business_b'}, {'action_key':'action-WRONG'},
    {'sys_id':'not-an-id'},
])
def test_wrong_lookup_correlation_cannot_confirm(change):
    with pytest.raises(ServiceNowContractError):
        call(lambda _:httpx.Response(200,json={'result':{'sys_id':SYSID,'tenant_id':TENANT,'action_key':KEY, **change}}), lookup=True)


def test_404_lookup_does_not_confirm_write():
    assert call(lambda _:httpx.Response(404), lookup=True) is None


@pytest.mark.parametrize('status', [200, 201, 202, 301, 401, 403, 429, 502])
def test_no_unconfirmed_post_status_as_success(status):
    r = reply() if status in (200, 201) else httpx.Response(status)
    if status in (200, 201):
        assert call(lambda _:httpx.Response(status,json={'result':{'sys_id':SYSID, 'tenant_id':TENANT, 'action_key':KEY}})) == SYSID
    else:
        with pytest.raises(ServiceNowUncertainWrite):
            call(lambda _:r)


def test_legacy_routes_only_opt_in_local():
    source = Path('app/main.py').read_text()
    assert "ENABLE_INSECURE_DEMO_ROUTES" in source
    assert "DEPLOYMENT_ENV" in source
    assert 'if INSECURE_LOCAL_LABS:' in source
    assert 'app.include_router(governance_router)' in source
    assert 'Depends(require_principal)' in source


def test_entra_without_business_mapping_denied(monkeypatch):
    monkeypatch.setenv('ENTRA_TENANT_ID','11111111-1111-1111-1111-111111111111')
    monkeypatch.setenv('ENTRA_API_AUDIENCE','api://valid-audience')
    monkeypatch.setenv('BUSINESS_TENANT_MEMBERSHIP_JSON','{}')
    with patch('app.v1_identity.jwks_client') as keys, patch('app.v1_identity.jwt.decode') as decode:
        keys.return_value.get_signing_key_from_jwt.return_value.key='key'
        decode.return_value={'tid':'11111111-1111-1111-1111-111111111111','oid':'oid-1','roles':['Agent.Operator']}
        with pytest.raises(HTTPException) as exc:
            verify_token('header.payload.signature')
    assert exc.value.status_code == 403


def test_business_tenant_independent_of_entra_tid(monkeypatch):
    monkeypatch.setenv('ENTRA_TENANT_ID','11111111-1111-1111-1111-111111111111')
    monkeypatch.setenv('ENTRA_API_AUDIENCE','api://valid-audience')
    monkeypatch.setenv('BUSINESS_TENANT_MEMBERSHIP_JSON','{"oid-1":"customer_acme"}')
    with patch('app.v1_identity.jwks_client') as keys, patch('app.v1_identity.jwt.decode') as decode:
        keys.return_value.get_signing_key_from_jwt.return_value.key='key'
        decode.return_value={'tid':'11111111-1111-1111-1111-111111111111','oid':'oid-1','roles':['Agent.Operator']}
        assert verify_token('header.payload.signature').tenant == 'customer_acme'


def test_worker_quarantine_and_reconciliation_guards():
    src=Path('app/reliability/governed_worker.py').read_text()
    assert 'if attempt > 1:' in src
    assert "status='UNCERTAIN'" in src
    assert 'SERVICENOW_DEDUP_CERTIFIED' in src
    assert 'SERVICENOW_PROVIDER_MODE' in src


def test_local_db_has_distinct_roles_and_rls():
    cfg=Path('docker-compose.v2.yml').read_text()
    assert 'agent_runtime_lab:runtime-local-only@postgres' in cfg
    assert 'agent_checkpoint_lab:checkpoint-local-only@postgres' in cfg
    assert 'agent:agent-local@postgres' not in cfg
    roles=Path('governance/reliability_roles.sql').read_text()
    assert roles.count('NOBYPASSRLS') >= 2
    assert 'agent_checkpoints' in roles


def test_api_routes_closed_without_lab_opt_in(monkeypatch):
    pytest.importorskip('langgraph')
    pytest.importorskip('psycopg')
    monkeypatch.delenv('ENABLE_INSECURE_DEMO_ROUTES', raising=False)
    monkeypatch.setenv('DEPLOYMENT_ENV', 'azure')
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    for path in ('/governance/actions', '/durable/runs', '/v1/runs'):
        assert c.post(path, json={}).status_code == 404
    assert c.post('/risk/analyze', json={'account_id':'ACME'}).status_code == 401
    assert c.post('/v2/runs', json={'account_id':'ACME'}).status_code == 401
    assert c.get('/metrics').status_code == 401
