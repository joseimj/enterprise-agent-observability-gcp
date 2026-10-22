variable "project_id" {
    type = string }
variable "region" {
    type = string
    default = "us-central1" }
variable "environment" {
    type = string
    default = "lab" }
variable "api_image" {
    type = string
    description = "Already-published image URI in Artifact Registry (do not use :latest for production)" }
variable "db_instance_name" {
    type = string
    default = "eao-gcp-v3-db" }
variable "db_tier" {
    type = string
    default = "db-custom-1-3840" }
variable "db_deletion_protection" {
    type = bool
    default = false
    description = "Set true outside disposable labs" }
variable "audit_dsn_secret" {
    type = string
    default = "eao-audit-dsn" }
variable "checkpoint_dsn_secret" {
    type = string
    default = "eao-checkpoint-dsn" }
variable "authz_registry_secret" {
    type = string
    default = "eao-authz-registry" }
variable "inference_provider" {
    type = string
    default = "offline"
    validation {
    condition = contains(["offline", "vertex"], var.inference_provider)
    error_message = "Use offline or vertex" } }
variable "gemini_model" {
    type = string
    default = "gemini-2.5-flash" }
variable "enable_worker" {
    type = bool
    default = false
    description = "Requires a separately deployed private simulator endpoint" }
variable "simulator_url" {
    type = string
    default = "" }
variable "worker_tenant" {
    type = string
    default = "acme" }
variable "worker_schedule" {
    type = string
    default = "*/5 * * * *" }
