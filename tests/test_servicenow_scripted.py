import asyncio
import httpx
import pytest
from app.connectors.governed_servicenow import ProviderAction
from app.connectors.servicenow import ServiceNowUncertainWrite, ServiceNowContractError
from app.connectors.servicenow_scripted import ServiceNowScriptedProvider

ID = '0123456789abcdef0123456789abcdef'
ACTION = ProviderAction(action_key='run-000001', tenant_id='tenantA',
    short_description='Critical operational risk', description='Evidence from case and issues')
BASE = 'https://dev123.service-now.com'

def run(coro): return asyncio.run(coro)

def provider(handler, enabled=True):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ServiceNowScriptedProvider(BASE, lambda: 'fake-token', client, enabled=enabled), client

def test_safe_by_default():
    p,c = provider(lambda r: httpx.Response(200, json={'result':{'sys_id':ID,'tenant_id':'tenantA','action_key':'run-000001'}}), enabled=False)
    with pytest.raises(PermissionError): run(p.create_once(ACTION))
    run(c.aclose())

def test_create_and_lookup_contract():
    calls=[]
    def handler(r):
        calls.append((r.method,str(r.url)))
        if r.method == 'POST':
            assert r.headers['authorization'] == 'Bearer fake-token'
            assert __import__('json').loads(r.content)['tenant_id'] == 'tenantA'
        return httpx.Response(200,json={'result':{'sys_id':ID,'number':'INC001','tenant_id':'tenantA','action_key':'run-000001'}})
    p,c=provider(handler)
    assert run(p.create_once(ACTION)) == ID
    assert run(p.lookup_by_key('run-000001','tenantA')) == ID
    assert calls[0][1].endswith('/api/x_oai_agent/v1/incidents')
    assert calls[1][1].endswith('/api/x_oai_agent/v1/incidents/tenantA/run-000001')
    run(c.aclose())

def test_duplicate_confirmation():
    p,c=provider(lambda r:httpx.Response(200,json={'result':{'sys_id':ID,'tenant_id':'tenantA','action_key':'run-000001'}}))
    assert run(p.create_once(ACTION)) == run(p.create_once(ACTION))
    run(c.aclose())

def test_conflict_rejected():
    p,c=provider(lambda r:httpx.Response(409,json={'result':{'error':'conflict'}}))
    with pytest.raises(ServiceNowContractError): run(p.create_once(ACTION))
    run(c.aclose())

def test_timeout_is_uncertain_then_lookup():
    def handler(r):
        if r.method=='POST': raise httpx.ReadTimeout('lost response')
        return httpx.Response(200,json={'result':{'sys_id':ID,'tenant_id':'tenantA','action_key':'run-000001'}})
    p,c=provider(handler)
    with pytest.raises(ServiceNowUncertainWrite):run(p.create_once(ACTION))
    assert run(p.lookup_by_key(ACTION.action_key,ACTION.tenant_id)) == ID
    run(c.aclose())

def test_missing_lookup_does_not_claim_success():
    p,c=provider(lambda r:httpx.Response(404,json={'error':'missing'}))
    assert run(p.lookup_by_key(ACTION.action_key,ACTION.tenant_id)) is None
    run(c.aclose())

def test_forbidden_tenant():
    from app.connectors.servicenow import ServiceNowForbidden
    p,c=provider(lambda r:httpx.Response(403,json={'error':'forbidden'}))
    with pytest.raises(ServiceNowForbidden):run(p.lookup_by_key(ACTION.action_key,ACTION.tenant_id))
    run(c.aclose())

def test_reject_invalid_path_tokens():
    p,c=provider(lambda r: (_ for _ in ()).throw(AssertionError('request must not occur')))
    with pytest.raises(ValueError):run(p.lookup_by_key('../another-tenant','tenantA'))
    with pytest.raises(ValueError):run(p.lookup_by_key('run-000001','../tenant'))
    run(c.aclose())

def test_reject_untrusted_host():
    with pytest.raises(ValueError):
        ServiceNowScriptedProvider('http://localhost',lambda:'token',None)
