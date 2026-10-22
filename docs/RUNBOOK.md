# Local Operations and Troubleshooting

## Start and verify
`docker compose up --build -d` then `docker compose ps` and `curl http://localhost:8000/health`. PostgreSQL initializes `governance/schema.sql` on the first volume creation. Grafana: http://localhost:3000; API docs: http://localhost:8000/docs.

## Dynatrace
Use the inherited `docker-compose.dynatrace.yml` overlay and `.env.example` from v0.3. Configure a valid OTLP endpoint and API token. Keep tokens out of Git. Dual export may increase telemetry egress and cost. Do not assume Davis AI or alert workflows are auto-provisioned.

## Debugging
- Database connection errors: `docker compose logs postgres api`; confirm PostgreSQL health.
- No audit events: use the governance API, not only `/risk/analyze`; the v0.3 analysis path has not been refactored through the new gateway.
- Missing trace ID: verify OTel Collector and API instrumentation. Audit events still persist without a valid trace.
- Lost credentials: never place secrets in logs, request bodies or Git.

## Recovery
Database volume is persistent across container restarts. `docker compose down -v` **deletes audit data**. Back up the database before any destructive reset. This is a lab, not a production disaster recovery solution.
