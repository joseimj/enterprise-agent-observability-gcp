# Change log — GCP extension

## v3.0 (2026-10-21)

- Forked additive GCP edition from `enterprise-agent-observability-recovery-validated.zip`.
- Retained historical Azure repository, PostgreSQL checkpointing, LangGraph
  approval interrupts, transactional one-time approvals and fenced outbox.
- Added verified-IAP-assertion API and signed-subject-to-tenant grants with
  operator/approver separation.
- Added read-only Vertex AI Gemini status explainer through Google Gen AI SDK,
  and optional post-commit Pub/Sub notification.
- Added Cloud Run/Cloud SQL/Secret Manager/IAP/PubSub/Artifact Registry
  Terraform scaffold and optional bounded Cloud Run worker job/Scheduler.
- Added 9 offline tests; no cloud, Docker or PostgreSQL test claim.
