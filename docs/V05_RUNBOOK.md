# v0.5 Operations Runbook

## Local startup

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8000/health
curl -X POST http://localhost:8000/risk/analyze -H 'Content-Type: application/json' -d '{"account_id":"ACME","scenario":"normal"}'
```

## Failure injection

```bash
curl -X POST http://localhost:8000/risk/analyze -H 'Content-Type: application/json' -d '{"account_id":"ACME","scenario":"servicenow_failure"}'
curl -X POST http://localhost:8000/risk/analyze -H 'Content-Type: application/json' -d '{"account_id":"ACME","scenario":"slow_servicenow"}'
```

Check API logs with `docker compose logs api servicenow` and traces in Grafana at `http://localhost:3000`. Dynatrace dual export: `docker compose -f docker-compose.yml -f docker-compose.dynatrace.yml up --build -d` after supplying tenant endpoint and API token. Never commit `.env`.

## Vendor deployments

Salesforce: deploy `integrations/salesforce` with Salesforce CLI to a sandbox and run Apex tests. Jira: choose Cloud or Data Center examples according to ScriptRunner deployment; do not run DC policy/listener in Cloud. ServiceNow: create a scoped application, custom customer reference field, Script Include, Scripted REST route, REST ACLs, event registry and ATF tests in a sub-production instance. Production integrations require OAuth, paging, rate limiting, retry policy and schema normalization.

## Verification

```bash
python -m compileall -q app tests
pytest -q tests/test_v05.py
```

Docker, Apex tests, Groovy tests, ServiceNow ATF and remote Dynatrace are separate validation gates and cannot be inferred from local Python tests.
