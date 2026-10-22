"""Fenced, audited outbox dispatch with conservative ambiguity handling.

No LangGraph node performs writes.  Only a worker using an independently
certified provider-side idempotency contract may enable real ServiceNow POSTs.
All external effects occur outside a PostgreSQL transaction; the outbox offers
at-least-once delivery, not exactly-once execution.  Unknown states are parked.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import psycopg
from opentelemetry import trace

from app.connectors.servicenow import ServiceNowError, ServiceNowContractError
from app.connectors.servicenow_scripted import ServiceNowScriptedProvider
from app.connectors.governed_servicenow import ProviderAction
from app.reliability.simulator_provider import SimulatorProvider
from app.v1_audit import record
from app.v2_worker import claim, finish

TRACER = trace.get_tracer('governed.provider.dispatcher')
TOOL = 'servicenow.incident.create'



@asynccontextmanager
async def configured_provider(*, fault_mode: str = 'none') -> AsyncIterator:
    mode = os.getenv('SERVICENOW_PROVIDER_MODE', 'simulator').lower()
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        if mode == 'simulator':
            yield SimulatorProvider(os.getenv('SIMULATOR_URL', 'http://servicenow-simulator:8010'),
                                    client, fault_mode)
        elif mode == 'scripted':
            if (os.getenv('ENABLE_SERVICENOW_REAL_WRITES') != 'true' or
                os.getenv('SERVICENOW_DEDUP_CERTIFIED') != 'true'):
                raise PermissionError('Real provider not enabled or provider deduplication not certified')
            origin = os.environ['SERVICENOW_ORIGIN']
            bearer = os.environ['SERVICENOW_OAUTH_BEARER_TOKEN']
            yield ServiceNowScriptedProvider(origin, lambda: bearer, client, enabled=True)
        else:
            raise ValueError('Unknown ServiceNow provider mode; default is simulator')


def _park(conn, tenant: str, item_id, run_id, key: str, attempt: int, reason: str):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
    row = conn.execute('''UPDATE v11_outbox SET status='UNCERTAIN',leased_until=NULL
        WHERE tenant_id=%s AND id=%s AND status='IN_PROGRESS' AND attempts=%s
          AND leased_until > now() RETURNING id''', (tenant, item_id, attempt)).fetchone()
    if row:
        record(conn, tenant, str(run_id), 'PROVIDER_OUTCOME_UNCERTAIN', 'governed-worker',
               {'action_key': key, 'reason': reason, 'operator_review_required': True})
    return {'status': 'UNCERTAIN' if row else 'STALE_LEASE', 'action_key': key}


def _confirm(conn, tenant: str, item_id, run_id, key: str, attempt: int,
             provider_id: str, mode: str):
    result = finish(conn, tenant, item_id, attempt)
    if result:
        record(conn, tenant, str(run_id), 'PROVIDER_CONFIRMED', 'governed-worker',
               {'action_key': key, 'provider_id': provider_id,
                'provider_mode': mode, 'attempt': attempt})
    return {'status': 'CONFIRMED' if result else 'STALE_LEASE',
            'action_key': key, 'provider_id': provider_id if result else None}


def _action(tenant: str, key: str, payload: dict) -> ProviderAction:
    if not isinstance(payload, dict) or payload.get('tool') != TOOL:
        raise ValueError('Outbox payload failed allowlist check')
    summary = payload.get('short_description')
    description = payload.get('description') or f"Investigate customer risk for account {payload.get('account_id', '')}"
    if not isinstance(summary, str) or not 1 <= len(summary) <= 160:
        raise ValueError('Invalid outbox short description')
    if not isinstance(description, str) or not 1 <= len(description) <= 4000:
        raise ValueError('Invalid outbox description')
    return ProviderAction(action_key=key, tenant_id=tenant,
                          short_description=summary, description=description,
                          account_id=str(payload.get('account_id', 'UNKNOWN')))


async def dispatch_once(tenant: str, provider=None, *, fault_mode: str = 'none') -> dict:
    """Claim one trusted-tenant job. Never resend after an unconfirmed attempt.

    Provider injection is intended for offline tests.  In production, the
    trusted worker service resolves the tenant from its deployment registry.
    """
    from app.connectors.servicenow_scripted import TENANT
    if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
        raise ValueError('Invalid trusted worker tenant')
    mode = 'injected' if provider is not None else os.getenv('SERVICENOW_PROVIDER_MODE', 'simulator')
    # Important: fail on provider configuration BEFORE acquiring any outbox lease.
    if provider is None:
        async with configured_provider(fault_mode=fault_mode) as configured:
            return await dispatch_once(tenant, provider=configured, fault_mode=fault_mode)

    with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
        item = claim(db, tenant)
    if item is None:
        return {'status': 'EMPTY'}
    item_id, run_id, tool, payload, key, attempt = item

    with TRACER.start_as_current_span('governed.external_dispatch') as span:
        span.set_attribute('agent.run_id', str(run_id))
        span.set_attribute('agent.tenant_id', tenant)
        span.set_attribute('outbox.attempt', attempt)
        if tool != TOOL:
            with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
                return _park(db, tenant, item_id, run_id, key, attempt, 'unsupported_tool')
        try:
            action = _action(tenant, key, payload)
        except ValueError:
            with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
                return _park(db, tenant, item_id, run_id, key, attempt, 'invalid_payload')

        # Reclaimed/expired lease: it may already have committed externally.
        # A missing lookup is NOT permission to post again.
        if attempt > 1:
            try:
                found = await provider.lookup_by_key(key, tenant)
            except (ServiceNowError, ValueError, KeyError):
                found = None
            with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
                if found:
                    return _confirm(db, tenant, item_id, run_id, key, attempt, found, mode)
                return _park(db, tenant, item_id, run_id, key, attempt, 'reclaimed_lease_unconfirmed')

        try:
            provider_id = await provider.create_once(action)
        except ServiceNowContractError:
            # A 409 means this key was used with a different payload.  Looking
            # up the existing key would silently certify the WRONG action.
            with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
                return _park(db, tenant, item_id, run_id, key, attempt, 'provider_contract_conflict')
        except (ServiceNowError, ValueError, KeyError, PermissionError):
            # When POST may have committed, authoritative lookup is the only
            # route to confirmation; never turn a lookup 404 into a resend.
            try:
                provider_id = await provider.lookup_by_key(key, tenant)
            except (ServiceNowError, ValueError, KeyError):
                provider_id = None
            if not provider_id:
                with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
                    return _park(db, tenant, item_id, run_id, key, attempt, 'post_result_unconfirmed')

        with psycopg.connect(os.environ['AUDIT_DATABASE_URL']) as db:
            return _confirm(db, tenant, item_id, run_id, key, attempt, provider_id, mode)


if __name__ == '__main__':
    tenant = os.environ['WORKER_BUSINESS_TENANT_ID']  # trusted deployment configuration
    print(asyncio.run(dispatch_once(tenant)))
