terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
    source = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}
provider "google" {
    project = var.project_id
    region = var.region }

data "google_project" "current" {
    project_id = var.project_id }
locals {
  prefix = "eao-${var.environment}"
  apis = toset([
    "run.googleapis.com", "sqladmin.googleapis.com", "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com", "secretmanager.googleapis.com",
    "pubsub.googleapis.com", "iap.googleapis.com", "cloudtrace.googleapis.com",
    "logging.googleapis.com", "cloudscheduler.googleapis.com"
  ])
}
resource "google_project_service" "apis" {
  for_each = local.apis
  project = var.project_id
  service = each.value
  disable_on_destroy = false
}

resource "google_service_account" "agent" {
  account_id = "${local.prefix}-api"
  display_name = "Enterprise agent API Cloud Run identity"
}
resource "google_service_account" "worker" {
  account_id = "${local.prefix}-worker"
  display_name = "Enterprise agent governed worker identity"
}
resource "google_service_account" "scheduler" {
  account_id = "${local.prefix}-scheduler"
  display_name = "Scheduler executor of guarded worker job"
}

resource "google_artifact_registry_repository" "images" {
  repository_id = "${local.prefix}-images"
  location = var.region
  format = "DOCKER"
  depends_on = [google_project_service.apis]
}
resource "google_sql_database_instance" "state" {
  name = var.db_instance_name
  database_version = "POSTGRES_16"
  region = var.region
  deletion_protection = var.db_deletion_protection
  settings {
    tier = var.db_tier
    availability_type = "ZONAL" # Lab economics; use REGIONAL for production HA.
    backup_configuration {
    enabled = true
    }
    ip_configuration {
      ipv4_enabled = true
      # No authorized networks. Cloud Run uses the Cloud SQL socket/proxy.
    }
  }
  depends_on = [google_project_service.apis]
}
resource "google_sql_database" "application" {
  name = "eao"
  instance = google_sql_database_instance.state.name
}

# Secrets are prepared externally; Terraform never stores the DB passwords
# or the subject-to-business-tenant registry in its state.
data "google_secret_manager_secret" "audit" {
    secret_id = var.audit_dsn_secret
    depends_on = [google_project_service.apis] }
data "google_secret_manager_secret" "checkpoint" {
    secret_id = var.checkpoint_dsn_secret
    depends_on = [google_project_service.apis] }
data "google_secret_manager_secret" "authz" {
    secret_id = var.authz_registry_secret
    depends_on = [google_project_service.apis] }
resource "google_secret_manager_secret_iam_member" "api_audit" {
  secret_id = data.google_secret_manager_secret.audit.id
  role = "roles/secretmanager.secretAccessor"
  member = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_secret_manager_secret_iam_member" "api_checkpoint" {
  secret_id = data.google_secret_manager_secret.checkpoint.id
  role = "roles/secretmanager.secretAccessor"
  member = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_secret_manager_secret_iam_member" "api_authz" {
  secret_id = data.google_secret_manager_secret.authz.id
  role = "roles/secretmanager.secretAccessor"
  member = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_secret_manager_secret_iam_member" "worker_audit" {
  count = var.enable_worker ? 1 : 0
  secret_id = data.google_secret_manager_secret.audit.id
  role = "roles/secretmanager.secretAccessor"
  member = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_project_iam_member" "api_cloudsql" {
  project = var.project_id
    role = "roles/cloudsql.client"
  member = "serviceAccount:${google_service_account.agent.email}"
}
resource "google_project_iam_member" "worker_cloudsql" {
  count = var.enable_worker ? 1 : 0
  project = var.project_id
    role = "roles/cloudsql.client"
  member = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_project_iam_member" "api_vertex" {
  count = var.inference_provider == "vertex" ? 1 : 0
  project = var.project_id
    role = "roles/aiplatform.user"
  member = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_pubsub_topic" "signals" {
  name = "${local.prefix}-outbox-notification"
  depends_on = [google_project_service.apis]
}
resource "google_pubsub_topic_iam_member" "publisher" {
  topic = google_pubsub_topic.signals.id
  role = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name = "${local.prefix}-api"
  location = var.region
  ingress = "INGRESS_TRAFFIC_ALL"
  # Require Cloud Run direct IAP; app ALSO verifies the signed IAP JWT.
  iap_enabled = true
  deletion_protection = false
  template {
    service_account = google_service_account.agent.email
    scaling {
    min_instance_count = 0
    max_instance_count = 3 }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
    instances = [google_sql_database_instance.state.connection_name] }
    }
    volumes {
      name = "authorization"
      secret {
        secret = data.google_secret_manager_secret.authz.secret_id
        items {
    version = "1"
    path = "registry.json" }
      }
    }
    containers {
      image = var.api_image
      ports {
    container_port = 8080 }
      resources {
    limits = {
    cpu = "1"
    memory = "1Gi" } }
      volume_mounts {
    name = "cloudsql"
    mount_path = "/cloudsql" }
      volume_mounts {
    name = "authorization"
    mount_path = "/secrets" }
      env {
    name = "GCP_IAP_AUDIENCE"
    value = "/projects/${data.google_project.current.number}/locations/${var.region}/services/${local.prefix}-api" }
      env {
    name = "GCP_AUTHZ_REGISTRY_PATH"
    value = "/secrets/registry.json" }
      env {
    name = "GOOGLE_CLOUD_PROJECT"
    value = var.project_id }
      env {
    name = "GOOGLE_CLOUD_LOCATION"
    value = var.region }
      env {
    name = "GCP_INFERENCE_PROVIDER"
    value = var.inference_provider }
      env {
    name = "GCP_GEMINI_MODEL"
    value = var.gemini_model }
      env {
    name = "GCP_PUBSUB_TOPIC"
    value = google_pubsub_topic.signals.id }
      env {
        name = "AUDIT_DATABASE_URL"
        value_source { secret_key_ref {
    secret = data.google_secret_manager_secret.audit.secret_id
    version = "1" } }
      }
      env {
        name = "CHECKPOINT_DATABASE_URL"
        value_source { secret_key_ref {
    secret = data.google_secret_manager_secret.checkpoint.secret_id
    version = "1" } }
      }
    }
  }
  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.api_audit,
    google_secret_manager_secret_iam_member.api_checkpoint,
    google_secret_manager_secret_iam_member.api_authz,
    google_project_iam_member.api_cloudsql
  ]
}
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project = var.project_id
  location = google_cloud_run_v2_service.api.location
  name = google_cloud_run_v2_service.api.name
  role = "roles/run.invoker"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

# Optional guarded worker is a JOB, not a publicly callable /dispatch endpoint.
resource "google_cloud_run_v2_job" "worker" {
  count = var.enable_worker ? 1 : 0
  name = "${local.prefix}-worker"
  location = var.region
  deletion_protection = false
  template {
    template {
      service_account = google_service_account.worker.email
      max_retries = 0 # Never blindly re-attempt an ambiguous external write.
      timeout = "300s"
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
    instances = [google_sql_database_instance.state.connection_name] }
      }
      containers {
        image = var.api_image
        command = ["python", "-m", "gcp_edition.worker"]
        volume_mounts {
    name = "cloudsql"
    mount_path = "/cloudsql" }
        env {
    name = "WORKER_BUSINESS_TENANT_ID"
    value = var.worker_tenant }
        env {
    name = "SERVICENOW_PROVIDER_MODE"
    value = "simulator" }
        env {
    name = "SIMULATOR_URL"
    value = var.simulator_url }
        env {
          name = "AUDIT_DATABASE_URL"
          value_source { secret_key_ref {
    secret = data.google_secret_manager_secret.audit.secret_id
    version = "1" } }
        }
      }
    }
  }
  lifecycle {
    precondition {
      condition = !var.enable_worker || startswith(var.simulator_url,"https://")
      error_message = "Worker requires a separately deployed HTTPS simulator; real writes are disabled."
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.worker_audit,google_project_iam_member.worker_cloudsql]
}
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  count = var.enable_worker ? 1 : 0
  project = var.project_id
  location = google_cloud_run_v2_job.worker[0].location
  name = google_cloud_run_v2_job.worker[0].name
  role = "roles/run.invoker"
  member = "serviceAccount:${google_service_account.scheduler.email}"
}
resource "google_cloud_scheduler_job" "worker" {
  count = var.enable_worker ? 1 : 0
  name = "${local.prefix}-worker-schedule"
  region = var.region
  schedule = var.worker_schedule
  time_zone = "Etc/UTC"
  http_target {
    http_method = "POST"
    uri = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.worker[0].name}:run"
    body = base64encode("{}")
    headers = { "Content-Type" = "application/json" }
    oauth_token {
    service_account_email = google_service_account.scheduler.email }
  }
  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker]
}

output "api_url" {
    value = google_cloud_run_v2_service.api.uri }
output "iap_audience" {
    value = "/projects/${data.google_project.current.number}/locations/${var.region}/services/${local.prefix}-api" }
output "cloudsql_instance_connection_name" {
    value = google_sql_database_instance.state.connection_name }
output "pubsub_topic" {
    value = google_pubsub_topic.signals.id }
output "artifact_registry" {
    value = google_artifact_registry_repository.images.id }
