variable "project" {
  description = "GCP project id"
  type        = string
}

variable "name" {
  description = "Prefix of the runtime service account id (<name>-runtime) and the data bucket name"
  type        = string
}

variable "deployer_service_account_email" {
  description = "Service account that CI deploys with; it is allowed to manage secret versions"
  type        = string
}

variable "secret_ids" {
  description = "Secret Manager secrets the function reads; their values are synced from GitHub secrets by CI"
  type        = list(string)
  default     = ["riot-api-key", "x-app-credentials", "accounts"]
}

variable "data_location" {
  description = "Location of the data bucket; US regions are covered by the Cloud Storage free tier"
  type        = string
  default     = "us-central1"
}

variable "data_soft_delete_days" {
  description = "Days that deleted objects in the data bucket can still be restored"
  type        = number
  default     = 30
}
