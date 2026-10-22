"""Read-only Salesforce OAuth client for Azure-hosted services.

Tokens are obtained using Salesforce OAuth client credentials flow; this is NOT
Azure managed identity authentication to Salesforce. Keep the client secret in
Azure Key Vault and inject it into the container securely.
"""
import os
import httpx
from pydantic import BaseModel, Field
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class SalesforceConfig(BaseModel):
    login_url: str = Field(pattern=r"^https://")
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    api_version: str = Field(default="v61.0", pattern=r"^v[0-9]+\.[0-9]+$")

    @classmethod
    def from_env(cls):
        return cls(login_url=os.environ['SALESFORCE_LOGIN_URL'].rstrip('/'),
                   client_id=os.environ['SALESFORCE_CLIENT_ID'],
                   client_secret=os.environ['SALESFORCE_CLIENT_SECRET'],
                   api_version=os.getenv('SALESFORCE_API_VERSION','v61.0'))

class SalesforceReadClient:
    def __init__(self, config: SalesforceConfig, transport=None):
        self.config=config
        self.transport=transport

    async def get_account(self, account_id: str) -> dict:
        # The account ID is constrained to Salesforce's 15/18-character alphanumeric ID.
        if len(account_id) not in (15,18) or not account_id.isalnum():
            raise ValueError('Expected Salesforce record ID (15 or 18 alphanumeric characters)')
        async with httpx.AsyncClient(timeout=12, transport=self.transport, follow_redirects=False) as client:
            with tracer.start_as_current_span('salesforce.oauth.token'):
                auth=await client.post(f'{self.config.login_url}/services/oauth2/token',data={
                    'grant_type':'client_credentials', 'client_id':self.config.client_id,
                    'client_secret':self.config.client_secret})
                auth.raise_for_status()
                token_data=auth.json()
                instance_url=token_data['instance_url'].rstrip('/')
                # Prevent untrusted OAuth responses from redirecting bearer tokens to arbitrary hosts.
                from urllib.parse import urlsplit
                host=urlsplit(instance_url)
                if host.scheme!='https' or not host.hostname or not (host.hostname.endswith('.salesforce.com') or host.hostname.endswith('.my.salesforce.com')) or host.username or host.password or host.port:
                    raise ValueError('Untrusted Salesforce instance URL')
            with tracer.start_as_current_span('salesforce.account.read') as span:
                span.set_attribute('crm.system','salesforce')
                response=await client.get(f'{instance_url}/services/data/{self.config.api_version}/sobjects/Account/{account_id}',
                    headers={'Authorization':f"Bearer {token_data['access_token']}"},params={'fields':'Id,Name,Industry'})
                response.raise_for_status()
                data=response.json()
                return {key:data.get(key) for key in ('Id','Name','Industry')}
