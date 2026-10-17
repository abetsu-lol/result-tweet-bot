variable "project" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "backend_bucket" {
  description = "GCS bucket name to store Terraform state (will be created during bootstrap)"
  type        = string
}
