"""Offline HTTP contract regressions for the tenant-aware simulator adapter."""
import asyncio

import httpx
import pytest

from app.connectors.governed_servicenow import ProviderAction
from app.connectors.servicenow import ServiceNowContractError, ServiceNowError, ServiceNowUncertainWrite
from app.reliability.simulator_provider import SimulatorProvider

ACTION = ProviderAction(
    action_key='action-000001', tenant_id='customer_a',
    short_description='Risk assessment requires investigation',
    description='Risk assessment', account_id='ACME',
)


def execute(handler, operation='post', *, tenant='customer_a'):
    async def task():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = SimulatorProvider('http://127.0.0.1:8010', client)
            if operation == 'post':
                return await provider.create_once(ACTION)
            return await provider.lookup_by_key(ACTION.action_key, tenant)
    return asyncio.run(task())


def response(*, tenant_id='customer_a', key='action-000001'):
    return {'tenant_id': tenant_id, 'idempotency_key': key, 'number': 'SIM-12345'}


def test_post_sends_tenant_and_idempotency_key():
    def handler(request):
        assert request.headers['Idempotency-Key'] == ACTION.action_key
        assert request.url.path == '/sim/incidents'
        assert request.method == 'POST'
        assert request.content and b'"tenant_id":"customer_a"' in request.content
        return httpx.Response(201, json=response())
    assert execute(handler) == 'SIM-12345'


def test_lookup_passes_tenant_as_query_parameter():
    def handler(request):
        assert request.method == 'GET'
        assert request.url.params['tenant_id'] == 'customer_a'
        return httpx.Response(200, json=response())
    assert execute(handler, 'get') == 'SIM-12345'


@pytest.mark.parametrize('mismatch', [
    {'tenant_id': 'customer_b'},
    {'idempotency_key': 'action-other'},
    {'number': ''},
])
def test_mismatched_post_cannot_be_confirmed(mismatch):
    with pytest.raises(ServiceNowUncertainWrite):
        execute(lambda _: httpx.Response(200, json={**response(), **mismatch}))


@pytest.mark.parametrize('mismatch', [
    {'tenant_id': 'customer_b'},
    {'idempotency_key': 'action-other'},
    {'number': ''},
])
def test_mismatched_lookup_cannot_be_confirmed(mismatch):
    with pytest.raises(ServiceNowError):
        execute(lambda _: httpx.Response(200, json={**response(), **mismatch}), 'get')


def test_conflicting_key_propagates_as_contract_error():
    with pytest.raises(ServiceNowContractError):
        execute(lambda _: httpx.Response(409, json={'detail': 'payload mismatch'}))


def test_commit_timeout_is_uncertain():
    with pytest.raises(ServiceNowUncertainWrite):
        execute(lambda _: httpx.Response(504))


def test_no_lookup_tenant_must_not_be_assumed():
    with pytest.raises(ServiceNowError):
        execute(lambda _: httpx.Response(200, json=response(tenant_id='customer_b')), 'get')


def test_404_lookup_is_not_permission_to_retry():
    assert execute(lambda _: httpx.Response(404), 'get') is None


def test_invalid_post_body_is_uncertain():
    with pytest.raises(ServiceNowUncertainWrite):
        execute(lambda _: httpx.Response(200, json=[]))


def test_invalid_lookup_body_is_rejected():
    with pytest.raises(ServiceNowError):
        execute(lambda _: httpx.Response(200, json=[]), 'get')


@pytest.mark.parametrize('url', [
    'https://127.0.0.1:8010',
    'http://127.0.0.1:8010@attacker.invalid',
    'http://servicenow-simulator:8010@attacker.invalid',
    'http://127.0.0.1:8010/redirect',
    'http://localhost:8010',
    'http://example.com:8010',
    'http://127.0.0.1:8010?tenant=evil',
])
def test_simulator_url_does_not_allow_external_destination(url):
    with pytest.raises(ValueError):
        SimulatorProvider(url, None)


def test_rejects_path_injection_in_action_key():
    async def task():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as c:
            sim = SimulatorProvider('http://127.0.0.1:8010', c)
            with pytest.raises(ValueError):
                await sim.lookup_by_key('../other_tenant', 'customer_a')
    asyncio.run(task())

def test_rejects_invalid_tenant_before_network_request():
    async def task():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as c:
            sim = SimulatorProvider('http://127.0.0.1:8010', c)
            with pytest.raises(ValueError):
                await sim.lookup_by_key('action-000001', 'business/a')
    asyncio.run(task())
