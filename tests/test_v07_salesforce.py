import pytest
import httpx
from app.salesforce_azure import SalesforceConfig, SalesforceReadClient

@pytest.mark.asyncio
async def test_salesforce_read_contract():
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/token'):
            return httpx.Response(200,json={'access_token':'dummy','instance_url':'https://demo.my.salesforce.com'})
        assert request.headers['Authorization']=='Bearer dummy'
        return httpx.Response(200,json={'Id':'001000000000001AAA','Name':'ACME','Industry':'Retail','Sensitive':'excluded'})
    config=SalesforceConfig(login_url='https://login.salesforce.com',client_id='id',client_secret='secret')
    result=await SalesforceReadClient(config,httpx.MockTransport(handler)).get_account('001000000000001AAA')
    assert result=={'Id':'001000000000001AAA','Name':'ACME','Industry':'Retail'}
    assert len(calls)==2

@pytest.mark.asyncio
async def test_reject_invalid_account_id():
    config=SalesforceConfig(login_url='https://login.salesforce.com',client_id='id',client_secret='secret')
    with pytest.raises(ValueError,match='record ID'):
        await SalesforceReadClient(config).get_account('../bad')

@pytest.mark.asyncio
async def test_reject_untrusted_instance_url():
    def handler(request):
        return httpx.Response(200,json={'access_token':'dummy','instance_url':'https://evil.example'})
    config=SalesforceConfig(login_url='https://login.salesforce.com',client_id='id',client_secret='secret')
    with pytest.raises(ValueError,match='Untrusted'):
        await SalesforceReadClient(config,httpx.MockTransport(handler)).get_account('001000000000001AAA')
