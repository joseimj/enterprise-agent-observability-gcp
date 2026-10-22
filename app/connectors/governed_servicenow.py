"""Adapter to worker contracts; writing is explicitly forbidden for Table API.

Real dispatch must use a provider-side idempotent Scripted REST endpoint,
with documented per-tenant ownership and an authoritative lookup by key.
"""
from dataclasses import dataclass
from typing import Protocol
from app.connectors.servicenow import ServiceNowTableAPI

@dataclass(frozen=True)
class ProviderAction:
    action_key: str
    tenant_id: str
    short_description: str
    description: str
    account_id: str = ''

class IdempotentIncidentProvider(Protocol):
    async def create_once(self, action:ProviderAction)->str: ...
    async def lookup_by_key(self, action_key:str, tenant_id:str)->str|None: ...

class StandardTableReadOnlyProvider:
    def __init__(self, api:ServiceNowTableAPI):self.api=api
    async def list_active(self):return await self.api.list_incidents(active=True)
    async def create_once(self, action:ProviderAction)->str:
        raise RuntimeError('Standard Table API is not a provider-side idempotent write contract')
    async def lookup_by_key(self, action_key:str, tenant_id:str)->str|None:
        raise RuntimeError('Standard Table API does not guarantee lookup by idempotency key')
