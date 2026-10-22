"""Contract-first ServiceNow Table API connector. No instance required for tests.

Writes are DISABLED by default. Standard Table API does not document native
idempotency. An uncertain write is not safe to retry without reconciliation.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit
import httpx

SYS_ID = re.compile(r"^[a-fA-F0-9]{32}$")
ALLOWED_INSTANCE = re.compile(r"^[a-zA-Z0-9-]+\.service-now\.com$")

class ServiceNowError(Exception):
    """Base connector error; messages deliberately exclude secrets/body."""

class ServiceNowUnauthorized(ServiceNowError): pass
class ServiceNowForbidden(ServiceNowError): pass
class ServiceNowNotFound(ServiceNowError): pass
class ServiceNowRateLimited(ServiceNowError): pass
class ServiceNowServerError(ServiceNowError): pass
class ServiceNowUncertainWrite(ServiceNowError): pass
class ServiceNowContractError(ServiceNowError): pass
class ServiceNowWriteDisabled(ServiceNowError): pass

@dataclass(frozen=True)
class Incident:
    sys_id: str
    number: str | None
    short_description: str | None
    raw: dict[str, Any]

class ServiceNowTableAPI:
    """Async adapter for documented GET/POST/PATCH Table API operations.

    Caller supplies a short-lived OAuth bearer token through token_provider;
    production token acquisition/rotation belongs in a managed identity/secret
    boundary. Pass an httpx.AsyncClient with MockTransport for offline tests.
    """
    def __init__(self, instance_url: str, token_provider: Callable[[], str],
                 client: httpx.AsyncClient, *, allow_writes: bool = False,
                 allow_custom_domains: bool = False):
        url = urlsplit(instance_url)
        host = url.hostname or ''
        if url.scheme != 'https' or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
            raise ValueError('ServiceNow instance URL must be an HTTPS origin')
        if not allow_custom_domains and not ALLOWED_INSTANCE.fullmatch(host):
            raise ValueError('ServiceNow instance hostname must be *.service-now.com')
        if not host or host in {'localhost', '127.0.0.1'}:
            raise ValueError('Invalid ServiceNow instance hostname')
        self.base_url = f'https://{host}' + (f':{url.port}' if url.port else '')
        self._token_provider = token_provider
        self.client = client
        self.allow_writes = allow_writes

    def _headers(self):
        token = self._token_provider()
        if not isinstance(token,str) or not token.strip():
            raise ServiceNowUnauthorized('OAuth bearer token unavailable')
        return {'Authorization':f'Bearer {token}','Accept':'application/json',
                'Content-Type':'application/json'}

    async def _send(self, method: str, path: str, *, params=None, json=None, write=False):
        if write and not self.allow_writes:
            raise ServiceNowWriteDisabled('Real ServiceNow writes are disabled')
        try:
            response = await self.client.request(method, self.base_url+path,
                                                 headers=self._headers(), params=params, json=json,
                                                 timeout=10.0, follow_redirects=False)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if write:
                raise ServiceNowUncertainWrite('Write outcome unknown; reconcile before retry') from exc
            raise ServiceNowError('ServiceNow network request failed') from exc
        status=response.status_code
        if status == 401: raise ServiceNowUnauthorized('ServiceNow returned 401')
        if status == 403: raise ServiceNowForbidden('ServiceNow returned 403')
        if status == 404: raise ServiceNowNotFound('ServiceNow returned 404')
        if status == 429: raise ServiceNowRateLimited('ServiceNow returned 429; honor Retry-After')
        if status >= 500:
            if write: raise ServiceNowUncertainWrite('ServiceNow 5xx; write may have committed')
            raise ServiceNowServerError('ServiceNow returned a server error')
        if status >= 300:
            if write: raise ServiceNowUncertainWrite(f'Unexpected status {status} after write')
            raise ServiceNowError(f'ServiceNow returned HTTP {status}')
        try: payload=response.json()
        except ValueError as exc: raise ServiceNowContractError('Invalid JSON response') from exc
        if not isinstance(payload,dict) or 'result' not in payload:
            raise ServiceNowContractError('Response missing result envelope')
        return payload['result']

    @staticmethod
    def _incident(value):
        if not isinstance(value,dict):
            raise ServiceNowContractError('Incident result must be an object')
        key=value.get('sys_id')
        if not isinstance(key,str) or not SYS_ID.fullmatch(key):
            raise ServiceNowContractError('Incident sys_id missing or invalid')
        return Incident(sys_id=key,number=value.get('number'),
                        short_description=value.get('short_description'),raw=value)

    async def get_incident(self, sys_id:str)->Incident:
        if not SYS_ID.fullmatch(sys_id): raise ValueError('Invalid incident sys_id')
        result=await self._send('GET',f'/api/now/v1/table/incident/{sys_id}',
                                params={'sysparm_fields':'sys_id,number,short_description,description,impact,urgency,state'})
        return self._incident(result)

    async def list_incidents(self, *, active:bool|None=True, limit:int=20, offset:int=0)->list[Incident]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError('Invalid pagination')
        params={'sysparm_limit':str(limit),'sysparm_offset':str(offset),
                'sysparm_fields':'sys_id,number,short_description,description,impact,urgency,state',
                'sysparm_display_value':'false'}
        if active is not None: params['sysparm_query']='active='+str(active).lower()
        result=await self._send('GET','/api/now/v1/table/incident',params=params)
        if not isinstance(result,list): raise ServiceNowContractError('List result must be an array')
        return [self._incident(x) for x in result]

    async def create_incident(self, *, short_description:str, description:str,
                              impact:str='2', urgency:str='2')->Incident:
        if not isinstance(short_description,str) or not 1 <= len(short_description) <= 160:
            raise ValueError('short_description must be 1–160 characters')
        if not isinstance(description,str) or not description.strip() or len(description)>4000:
            raise ValueError('description must be 1–4000 characters')
        if impact not in ('1','2','3') or urgency not in ('1','2','3'):
            raise ValueError('impact and urgency must be 1, 2 or 3')
        body={'short_description':short_description,'description':description,
              'impact':impact,'urgency':urgency}
        result=await self._send('POST','/api/now/v1/table/incident',json=body,write=True)
        return self._incident(result)

    async def update_incident(self, sys_id:str, *, short_description:str)->Incident:
        if not SYS_ID.fullmatch(sys_id): raise ValueError('Invalid incident sys_id')
        if not isinstance(short_description,str) or not 1<=len(short_description)<=160:
            raise ValueError('Invalid short description')
        result=await self._send('PATCH',f'/api/now/v1/table/incident/{sys_id}',
                                json={'short_description':short_description},write=True)
        return self._incident(result)
