"""Tenant-scoped HTTP client for the LOCAL-ONLY incident fault simulator.

No PostgreSQL runtime dependency: transport contracts can be tested offline.
The simulator is not ServiceNow and provides no authentication boundary.
"""
import httpx
import re
from urllib.parse import urlsplit
from app.connectors.servicenow import ServiceNowError, ServiceNowUncertainWrite, ServiceNowContractError
from app.connectors.governed_servicenow import ProviderAction

KEY = re.compile(r'[A-Za-z0-9_.:-]{8,128}')
TENANT = re.compile(r'[A-Za-z0-9_-]{1,64}')


class SimulatorProvider:
    """HTTP simulator adapter; never contacts a ServiceNow instance."""

    def __init__(self, url: str, client: httpx.AsyncClient, fault_mode: str = 'none'):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or
            parsed.hostname not in {'servicenow-simulator', '127.0.0.1'} or
            parsed.port is None or parsed.username or parsed.password or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('Simulator URL must be an explicit local HTTP endpoint')
        self.url = f'http://{parsed.hostname}:{parsed.port}'
        self.client = client
        self.fault_mode = fault_mode

    @staticmethod
    def _verify_identifiers(key: str, tenant: str) -> None:
        if (not isinstance(key, str) or not KEY.fullmatch(key) or
            not isinstance(tenant, str) or not TENANT.fullmatch(tenant)):
            raise ValueError('Invalid tenant or idempotency key')

    async def create_once(self, action: ProviderAction) -> str:
        self._verify_identifiers(action.action_key, action.tenant_id)
        try:
            response = await self.client.post(
                f'{self.url}/sim/incidents',
                headers={'Idempotency-Key': action.action_key, 'X-Fault-Mode': self.fault_mode},
                json={'tenant_id': action.tenant_id, 'account_id': action.account_id or 'UNKNOWN',
                      'summary': action.short_description}, timeout=5.0)
        except httpx.TransportError as exc:
            raise ServiceNowUncertainWrite('Simulator post transport uncertain') from exc
        if response.status_code == 409:
            raise ServiceNowContractError('Simulator idempotency conflict')
        if response.status_code not in (200, 201):
            raise ServiceNowUncertainWrite('Simulator post result uncertain')
        try:
            result = response.json()
        except ValueError as exc:
            raise ServiceNowUncertainWrite('Simulator post acknowledgement malformed') from exc
        if (not isinstance(result, dict) or result.get('tenant_id') != action.tenant_id or
            result.get('idempotency_key') != action.action_key or not result.get('number')):
            raise ServiceNowUncertainWrite('Simulator response correlation failed')
        return result['number']

    async def lookup_by_key(self, action_key: str, tenant_id: str) -> str | None:
        self._verify_identifiers(action_key, tenant_id)
        try:
            response = await self.client.get(f'{self.url}/sim/incidents/by-key/{action_key}',
                                             params={'tenant_id': tenant_id}, timeout=5.0)
        except httpx.TransportError as exc:
            raise ServiceNowError('Simulator lookup unavailable') from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ServiceNowError('Simulator lookup failed')
        try:
            result = response.json()
        except ValueError as exc:
            raise ServiceNowError('Simulator lookup response malformed') from exc
        if (not isinstance(result, dict) or result.get('tenant_id') != tenant_id or
            result.get('idempotency_key') != action_key or not result.get('number')):
            raise ServiceNowError('Simulator lookup correlation failed')
        return result['number']

