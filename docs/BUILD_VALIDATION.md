# Build-time Validation Record

**Artifact:** Enterprise Agent Observability — Recovery Validation Increment

The repository's updated offline contract and security regression command:

```bash
python -m pytest -q \
  tests/test_simulator_provider_contract.py \
  tests/test_security_remediation.py \
  tests/test_worker_dispatch_offline.py \
  tests/test_servicenow_scripted.py \
  tests/test_servicenow_contract_first.py
```

**Build-environment result:** `77 passed, 1 skipped`.
Python source compilation completed, Bash script syntax checked, and five
Compose/GitHub Actions YAML documents parsed successfully. The skipped test
requires dependencies not installed in the artifact-building environment.

**NOT EXECUTED:** Real PostgreSQL, LangGraph/PostgresSaver and HTTP simulator
integration tests in `tests/reliability/`, because Docker is not available
in the artifact-building container. A CI workflow and reproducible Docker
runner are provided, but this document does **not** claim those tests passed.

**NOT CERTIFIED:** Real ServiceNow ACLs/index consistency, live Entra tokens,
Azure PostgreSQL deployment/networking, Grafana/Dynatrace tracing, exactly-once
external side effects, or fully adversarial tenant isolation.

**Next gate:** Run `bash scripts/run_reliability_lab.sh` on a Docker-enabled
CI runner, fix any failures, and preserve actual test logs as release evidence.
