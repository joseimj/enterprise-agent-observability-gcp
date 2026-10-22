# Dynatrace integration and Davis AI

Use a Dynatrace tenant with OTLP HTTP ingestion enabled. Set `DT_OTLP_ENDPOINT` to the full tenant OTLP base endpoint documented in your environment (typically an `/api/v2/otlp` URL); the Collector appends `/v1/traces` or `/v1/logs`. Generate a token with the required `openTelemetryTrace.ingest` and `logs.ingest` permissions (confirm exact scopes against tenant docs). Do not commit tokens.

Run with the optional compose override. Inspect ingested traces/logs in Dynatrace and use `queries.dql` as starter templates; attribute names may differ by Grail schema/version.

**Davis AI**: Configure anomaly detection and a Davis problem notification/workflow *inside your tenant*. OTel ingestion alone does not guarantee automatic root cause analysis or problem creation; Davis requires appropriate service topology, detection rules, permissions, and licensing. Validate detected root causes against injected ground truth. For automation, require approval before any remediation action.

No Dynatrace tenant, credentials, Davis detection or workflow is provisioned by this repository.
