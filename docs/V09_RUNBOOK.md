# v0.9 — Local Runbook (English)

## Requirements

Docker Compose v2, Python 3.11+, PostgreSQL 16 image, and an accessible Docker daemon.

## Start local stack

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.durable.yml up --build -d
# Initialize LangGraph's PostgreSQL tables ONCE using an administrative connection:
docker compose -f docker-compose.yml -f docker-compose.durable.yml exec api python scripts/init_checkpointer.py
```

## Start a paused run

```bash
curl -s -X POST http://localhost:8000/durable/runs \
  -H 'Content-Type: application/json' -H 'X-Tenant-Id: demo' \
  -H 'X-Actor-Id: agent-1' -H 'X-Role: agent' \
  -d '{"account_id":"ACME"}'
```

Copy `run_id` from the JSON response. Inspect the checkpoint:

```bash
curl -s http://localhost:8000/durable/runs/REPLACE_RUN_ID \
  -H 'X-Tenant-Id: demo' -H 'X-Actor-Id: auditor-1' -H 'X-Role: auditor'
```

## Resume with human approval

```bash
curl -s -X POST http://localhost:8000/durable/runs/REPLACE_RUN_ID/decision \
  -H 'Content-Type: application/json' -H 'X-Tenant-Id: demo' \
  -H 'X-Actor-Id: human-1' -H 'X-Role: approver' \
  -d '{"approved":true}'
```

Expected result: `SIMULATED` and `external_write: false`. To test rejection, start a fresh run and send `{"approved":false}`.

## Verify persistence across restart

Start and pause a run, then run `docker compose ... restart api` and resume with the same run ID. The PostgreSQL volume must remain intact. **This restart scenario has not been executed in the authoring environment.**

## Azure review

```bash
cd infrastructure/azure
terraform init
terraform fmt -check
terraform validate
terraform plan
```

Review cost, state-file secrets, private DNS, Container Apps subnet, image registry authentication, and migration role design before `terraform apply`.
