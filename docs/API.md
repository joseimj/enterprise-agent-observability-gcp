# Governance API (development only)

Start `docker compose up --build -d`. Wait for PostgreSQL readiness. Example calls require `X-Tenant-Id`, `X-Actor-Id`, and `X-Role`. These are **untrusted demo headers**.

```bash
RUN_ID=$(python -c 'import uuid;print(uuid.uuid4())')
curl -sS -X POST localhost:8000/governance/actions \
 -H 'Content-Type: application/json' -H 'X-Tenant-Id: demo' \
 -H 'X-Actor-Id: agent-01' -H 'X-Role: agent' \
 -d "{\"run_id\":\"$RUN_ID\",\"tool_name\":\"jira.create_followup\",\"arguments\":{\"account_id\":\"ACME\",\"summary\":\"Review SLA risk\"},\"idempotency_key\":\"demo-run-001\"}"
```

Save the returned `action_id` as `ACTION_ID`. Then:

```bash
curl -sS -X POST "localhost:8000/governance/actions/$ACTION_ID/decision" \
 -H 'Content-Type: application/json' -H 'X-Tenant-Id: demo' \
 -H 'X-Actor-Id: reviewer-01' -H 'X-Role: approver' -d '{"approve":true}'
curl -sS -X POST "localhost:8000/governance/actions/$ACTION_ID/execute" \
 -H 'X-Tenant-Id: demo' -H 'X-Actor-Id: executor-01' -H 'X-Role: executor'
curl -sS "localhost:8000/governance/runs/$RUN_ID/events" \
 -H 'X-Tenant-Id: demo' -H 'X-Actor-Id: auditor-01' -H 'X-Role: auditor'
```

Expected events: `ACTION_REQUESTED`, `ACTION_DECISION`, `ACTION_EXECUTED_MOCK`. The execution response explicitly reports `external_write: false`.

## Negative scenarios
1. Use `approve:false`, then attempt execute: HTTP 409.
2. Attempt approval as `agent-01`: HTTP 409.
3. Query timeline using a different tenant: empty list.
4. Reuse the idempotency key with different arguments: HTTP 409.
5. Attempt an unknown tool: HTTP 409.
