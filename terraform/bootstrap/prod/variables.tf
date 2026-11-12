variable "project" {
  description = "GCP project id"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in the form 'owner/repo' that is allowed to deploy via Workload Identity Federation"
  type        = string
}

variable "tf_state_bucket" {
  description = "tfstate bucket (TF_STATE_BUCKET) that the planner service account may read"
  type        = string
}
