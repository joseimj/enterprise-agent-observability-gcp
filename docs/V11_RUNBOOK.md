# v1.1 Local Runbook

1. Start the existing v1.0 stack using the v1 compose overlay and initialize the checkpointer.
2. Apply `governance/v11_schema.sql` as the migration role to the existing `agent_audit` database. The Docker init scripts only execute on a fresh database volume; for an existing volume, apply SQL manually.
3. Seed an approval using `request_approval(conn, tenant_id, run_id)` from a trusted application transaction.
4. Consume it with `decide_once(conn, tenant_id, run_id, verified_approver, approved, tool, sanitized_payload)` and commit the transaction.
5. Run `python -m scripts.v11_worker TENANT_ID` inside the API container to process one simulated action.
6. Inspect `v11_approvals` and `v11_outbox` with tenant-scoped SQL sessions.

**Caution:** the new module is not yet mounted as a REST API. It does not perform real ServiceNow actions. Run `python -m unittest discover -s tests -p 'test_v11_contracts.py'` for isolated contract tests. End-to-end PostgreSQL, Azure, and SaaS integration tests remain outstanding.
