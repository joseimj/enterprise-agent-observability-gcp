# ServiceNow Contract-First Connector

## Scope

The connector implements an HTTP client for the **documented** ServiceNow Table API incident endpoints. Tests use `httpx.MockTransport` and require **no ServiceNow instance or credentials**. All example tokens are fake.

| Operation | Endpoint | Test scope |
|---|---|---|
| Read incident | `GET /api/now/v1/table/incident/{sys_id}` | request/response envelope and identity |
| List incidents | `GET /api/now/v1/table/incident` | `sysparm_query`, `sysparm_fields`, limit and offset |
| Create incident | `POST /api/now/v1/table/incident` | disabled by default; opt-in contract only |
| Update incident | `PATCH /api/now/v1/table/incident/{sys_id}` | disabled by default; opt-in contract only |

### Verified official references

- [Table API](https://www.servicenow.com/docs/r/xanadu/api-reference/rest-apis/c_TableAPI.html)
- [Create an incident record](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/t_GetStartedCreateInt.html)
- [Read the incident](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/t_GetStartedReadInt.html)
- [Update the incident](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/get-started-update-incident.html)

## Security and reliability boundaries

- `ServiceNowTableAPI(..., allow_writes=False)` refuses POST/PATCH by default.
- The governed adapter `StandardTableReadOnlyProvider` cannot execute outbox writes, **even when `allow_writes=True`** on the low-level API client.
- The Table API does not document a native idempotency-key guarantee. **Do not blindly retry uncertain writes.** A timeout or HTTP 5xx after POST results in `ServiceNowUncertainWrite`.
- Real governed writes require a reviewed, deployed ServiceNow Scripted REST endpoint (or another proven server-side deduplication contract) that persistently maps `(tenant, action_key)` to a unique incident. Its `lookup_by_key` must be authoritative, and failure to confirm must park the action for operator review.
- The module validates HTTPS origins and restricts hostnames to `*.service-now.com` by default. `allow_custom_domains` permits explicitly configured custom HTTPS hosts and must not be driven by user input. Deploy with egress allowlists and no redirects.
- Authentication integration expects bearer-token injection via `token_provider`; it does **not** implement OAuth token acquisition, rotation, RBAC, domain separation or ACL evaluation.
- The library does not automatically integrate with the existing `v2_worker.py` dispatch path. Replacing the existing simulator requires an explicit reviewed wiring change and tests against a real ServiceNow test instance.
- Customizations such as mandatory fields, ACLs, Business Rules, release-specific behavior and rate-limit policies cannot be certified offline.

## Run offline contract tests

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests/test_servicenow_contract_first.py
```

## Example read using a fake transport

```python
import asyncio, httpx
from app.connectors.servicenow import ServiceNowTableAPI

async def demo():
    sys_id = '0123456789abcdef0123456789abcdef'
    def handler(request):
        return httpx.Response(200, json={'result': {'sys_id': sys_id, 'number': 'INC001'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        api = ServiceNowTableAPI('https://dev123.service-now.com', lambda: 'fake-token', client)
        print((await api.get_incident(sys_id)).number)

asyncio.run(demo())
```

## Next acceptance gate

Implement a Scripted REST API with a provider-side uniqueness constraint for the idempotency key; test its duplicate/conflict and read-after-timeout behaviors; then add guarded dispatcher mode and full PostgreSQL integration tests. Never claim exactly-once ServiceNow writes from a client-only key.
