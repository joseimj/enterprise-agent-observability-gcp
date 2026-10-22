import asyncio
import httpx
import pytest
from app.connectors.servicenow import (ServiceNowTableAPI, ServiceNowForbidden,
    ServiceNowUncertainWrite, ServiceNowWriteDisabled, ServiceNowRateLimited,
    ServiceNowContractError)
from app.connectors.governed_servicenow import StandardTableReadOnlyProvider,ProviderAction
SID='0123456789abcdef0123456789abcdef'
BASE='https://dev123.service-now.com'
def run(coro):return asyncio.run(coro)
def adapter(handler,**kwargs):
    client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ServiceNowTableAPI(BASE,lambda:'fake-token',client,**kwargs)

def test_get_contract_auth_and_fields():
    def handler(request):
        assert request.url.path.endswith('/api/now/v1/table/incident/'+SID)
        assert request.headers['authorization']=='Bearer fake-token'
        assert 'sysparm_fields=' in str(request.url)
        return httpx.Response(200,json={'result':{'sys_id':SID,'number':'INC1001','short_description':'Risk'}})
    result=run(adapter(handler).get_incident(SID))
    assert result.number=='INC1001'

def test_paginated_list():
    def handler(request):
        assert request.url.params['sysparm_limit']=='5'
        assert request.url.params['sysparm_offset']=='10'
        assert request.url.params['sysparm_query']=='active=true'
        return httpx.Response(200,json={'result':[{'sys_id':SID,'number':'INC123'}]})
    assert len(run(adapter(handler).list_incidents(limit=5,offset=10)))==1

def test_default_denies_write_without_sending():
    def handler(request): raise AssertionError('No HTTP request expected')
    with pytest.raises(ServiceNowWriteDisabled):
        run(adapter(handler).create_incident(short_description='Risk',description='Details'))

def test_opt_in_post_contract():
    def handler(request):
        assert request.method=='POST'
        assert request.url.path=='/api/now/v1/table/incident'
        assert request.read().decode().find('short_description')>=0
        return httpx.Response(201,json={'result':{'sys_id':SID,'number':'INC99'}})
    result=run(adapter(handler,allow_writes=True).create_incident(short_description='Risk',description='Details'))
    assert result.sys_id==SID

def test_timeout_after_write_is_uncertain():
    def handler(request): raise httpx.ReadTimeout('lost response',request=request)
    with pytest.raises(ServiceNowUncertainWrite):
        run(adapter(handler,allow_writes=True).create_incident(short_description='Risk',description='Details'))

def test_5xx_write_is_uncertain():
    with pytest.raises(ServiceNowUncertainWrite):
        run(adapter(lambda r:httpx.Response(503),allow_writes=True).create_incident(short_description='Risk',description='Details'))

def test_429_read_has_distinct_error():
    with pytest.raises(ServiceNowRateLimited): run(adapter(lambda r:httpx.Response(429)).list_incidents())

def test_forbidden_read():
    with pytest.raises(ServiceNowForbidden):run(adapter(lambda r:httpx.Response(403)).list_incidents())

def test_missing_envelope_rejected():
    with pytest.raises(ServiceNowContractError):run(adapter(lambda r:httpx.Response(200,json={'foo':1})).list_incidents())

def test_invalid_endpoint_and_sysid_rejected():
    with pytest.raises(ValueError):adapter(lambda r:None,instance='x') if False else ServiceNowTableAPI('http://localhost',lambda:'test',httpx.AsyncClient())
    with pytest.raises(ValueError):run(adapter(lambda r:None).get_incident('123/../../'))

def test_governed_worker_cannot_use_standard_table_write():
    provider=StandardTableReadOnlyProvider(adapter(lambda r:None,allow_writes=True))
    with pytest.raises(RuntimeError,match='idempotent'):
        run(provider.create_once(ProviderAction('key','tenant','Risk','Details')))
