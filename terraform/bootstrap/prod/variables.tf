variable "project" {
  description = "GCP project id"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in the form 'owner/repo' that is allowed to deploy via Workload Identity Federation"
  type        = string
}
