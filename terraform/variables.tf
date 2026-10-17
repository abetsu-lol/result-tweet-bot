variable "project" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "daily-python-job"
}

variable "github_repository" {
  description = "GitHub repository in the form 'owner/repo' that is allowed to deploy via Workload Identity Federation"
  type        = string
}

variable "deploy_branch" {
  description = "Branch whose GitHub Actions runs are allowed to authenticate via Workload Identity Federation"
  type        = string
  default     = "main"
}

variable "ci_roles" {
  description = "Project roles granted to the GitHub Actions service account so that CI can run terraform apply"
  type        = list(string)
  default = [
    "roles/editor",
    "roles/iam.securityAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
  ]
}

variable "create_github_binding" {
  description = "If true, create the IAM binding that grants the GitHub principal access to the service account."
  type        = bool
  default     = true
}

variable "impersonate_service_account" {
  description = "(optional) Service account email to impersonate when running Terraform locally (uses ADC then impersonates). Empty to disable."
  type        = string
  default     = ""
}

variable "function_zip_path" {
  description = "Path to the Cloud Function source zip built by scripts/package_function.*"
  type        = string
  default     = "../build/function.zip"
}

variable "function_source_dir" {
  description = "Cloud Function source directory; must match what was packaged into function_zip_path"
  type        = string
  default     = "../cloud_function"
}
