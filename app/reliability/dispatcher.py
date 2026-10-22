"""Backward-compatible entrypoint to the hardened governed worker.

DEPRECATED: synchronous local simulator convenience wrapper.  There is one
canonical dispatch policy in app.reliability.governed_worker; never maintain a
second set of retry semantics here.
"""
import asyncio
from app.reliability.governed_worker import dispatch_once as dispatch_governed


def dispatch_once(tenant: str, fault_mode: str = 'none') -> dict:
    result = asyncio.run(dispatch_governed(tenant, fault_mode=fault_mode))
    if result.get('status') == 'UNCERTAIN':
        return {**result, 'requires_manual_reconciliation': True}
    return result
