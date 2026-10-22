"""Custom Scripted REST client; disabled until a reviewed endpoint is deployed.

The API relies on a *provider-side unique key* and tenant authorization.
This class itself cannot supply an exactly-once guarantee.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
import httpx
from app.connectors.governed_servicenow import ProviderAction
from app.connectors.servicenow import (ServiceNowUncertainWrite, ServiceNowUnauthorized,
    ServiceNowForbidden, ServiceNowRateLimited, ServiceNowContractError, ServiceNowError)

KEY = re.compile(r'^[A-Za-z0-9_.:-]{8,128}$')
TENANT = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
SYSID = re.compile(r'^[a-fA-F0-9]{32}$')

class ServiceNowScriptedProvider:
    def __init__(self, origin: str, token_provider, client: httpx.AsyncClient, *,
                 enabled: bool = False, api_path: str = '/api/x_oai_agent/v1/incidents',
                 allow_custom_domains: bool = False):
        parsed = urlsplit(origin)
        host = parsed.hostname or ''
        if (parsed.scheme != 'https' or parsed.username or parsed.password or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.port):
            raise ValueError('Expected a clean HTTPS ServiceNow origin')
        if not allow_custom_domains and not re.fullmatch(r'[A-Za-z0-9-]+\.service-now\.com', host):
            raise ValueError('Host must be a ServiceNow instance')
        if not host or host in ('localhost', '127.0.0.1'):
            raise ValueError('Invalid provider host')
        if not re.fullmatch(r'/api/[A-Za-z0-9_]+/v[0-9]+/incidents', api_path):
            raise ValueError('Unexpected scripted API path')
        self.url = 'https://' + host + api_path
        self.token_provider = token_provider
        self.client = client
        self.enabled = enabled

    def _headers(self):
        token = self.token_provider()
        if not isinstance(token, str) or not token.strip():
            raise ServiceNowUnauthorized('Bearer token missing')
        return {'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
                'Content-Type': 'application/json'}

    @staticmethod
    def _validate(key, tenant):
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise ValueError('Invalid action key')
        if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
            raise ValueError('Invalid tenant')

    async def _request(self, method, url, *, payload=None, tenant_id, action_key):
        """Only accept a confirmation correlated to the authorized action.

        Once POST has been attempted, an incomplete or mismatched acknowledgement
        is uncertain, not permission to retry.  GET errors cannot confirm absence
        except a 404 from the authoritative provider (still not retry permission).
        """
        try:
            response = await self.client.request(method, url, headers=self._headers(),
                         json=payload, timeout=10.0, follow_redirects=False)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if method == 'POST':
                raise ServiceNowUncertainWrite('Provider write outcome unknown') from exc
            raise ServiceNowError('Provider lookup transport unavailable') from exc

        status = response.status_code
        if method == 'POST':
            if status == 409:
                raise ServiceNowContractError('Idempotency key conflicts with another payload')
            if status not in (200, 201):
                # Conservatively quarantine even unexpected auth/error responses:
                # the upstream gateway could have forwarded the write first.
                raise ServiceNowUncertainWrite('Unconfirmed provider write response')
        else:
            if status == 404: return None
            if status == 401: raise ServiceNowUnauthorized('Lookup returned 401')
            if status == 403: raise ServiceNowForbidden('Lookup returned 403')
            if status == 429: raise ServiceNowRateLimited('Lookup returned 429')
            if status != 200: raise ServiceNowError('Lookup response not authoritative')

        try:
            envelope = response.json()
            result = envelope['result']
        except (ValueError, KeyError, TypeError) as exc:
            if method == 'POST':
                raise ServiceNowUncertainWrite('Unparseable provider acknowledgement') from exc
            raise ServiceNowContractError('Unparseable lookup response') from exc
        if not isinstance(result, dict):
            if method == 'POST':
                raise ServiceNowUncertainWrite('Unconfirmed provider result type')
            raise ServiceNowContractError('Lookup result is not an object')
        sys_id = result.get('sys_id')
        if (result.get('tenant_id') != tenant_id or
            result.get('action_key') != action_key or
            not isinstance(sys_id, str) or not SYSID.fullmatch(sys_id)):
            if method == 'POST':
                raise ServiceNowUncertainWrite('Provider acknowledgement correlation failed')
            raise ServiceNowContractError('Provider lookup correlation failed')
        return sys_id

    async def create_once(self, action: ProviderAction) -> str:
        if not self.enabled: raise PermissionError('Custom ServiceNow writes are disabled by default')
        self._validate(action.action_key, action.tenant_id)
        if not 1 <= len(action.short_description) <= 160 or not 1 <= len(action.description) <= 4000:
            raise ValueError('Invalid incident descriptions')
        # Tenant header is only a *claim*; ServiceNow must authenticate and authorize it.
        return await self._request('POST', self.url, tenant_id=action.tenant_id,
                                   action_key=action.action_key, payload={
            'tenant_id': action.tenant_id, 'action_key': action.action_key,
            'short_description': action.short_description, 'description': action.description})

    async def lookup_by_key(self, action_key: str, tenant_id: str) -> str | None:
        self._validate(action_key, tenant_id)
        # No path interpolation of tenant/key: fixed-length constrained tokens only.
        return await self._request('GET', self.url + '/' + tenant_id + '/' + action_key,
                                   tenant_id=tenant_id, action_key=action_key)
