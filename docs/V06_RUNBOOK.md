# v0.6 Runbook (Local Lab)

## Start
```bash
cp .env.example .env
docker compose up --build -d
```

## Create an action
```bash
RUN_ID=$(python -c 'import uuid;print(uuid.uuid4())')
curl -X POST http://localhost:8000/governance/actions \
 -H 'Content-Type: application/json' -H 'X-Tenant-Id: demo' \
 -H 'X-Actor-Id: agent-1' -H 'X-Role: agent' \
 -d "{\"run_id\":\"$RUN_ID\",\"tool_name\":\"servicenow.create_incident\",\"arguments\":{\"account_id\":\"ACME\",\"summary\":\"Payments API outage\",\"priority\":\"2\"},\"idempotency_key\":\"demo-$RUN_ID\"}"
```
Copy `action_id` from the response.

## Approve, simulate execution, inspect timeline
```bash
curl -X POST http://localhost:8000/governance/actions/$ACTION_ID/decision \
 -H 'Content-Type: application/json' -H 'X-Tenant-Id: demo' \
 -H 'X-Actor-Id: reviewer-1' -H 'X-Role: approver' -d '{"approve":true}'
curl -X POST http://localhost:8000/governance/actions/$ACTION_ID/execute \
 -H 'X-Tenant-Id: demo' -H 'X-Actor-Id: worker-1' -H 'X-Role: executor'
curl http://localhost:8000/governance/runs/$RUN_ID/explorer \
 -H 'X-Tenant-Id: demo' -H 'X-Actor-Id: auditor-1' -H 'X-Role: auditor'
```

## Expected results
PENDING -> APPROVED -> EXECUTED (mock only). Audit events: ACTION_REQUESTED, ACTION_DECISION, ACTION_EXECUTED_MOCK. No live ServiceNow record is created.

## Known gaps
Docker execution, real Salesforce/Jira/ServiceNow credentials, LangGraph checkpointing, verified authentication, and external write reconciliation require additional work and validation.
