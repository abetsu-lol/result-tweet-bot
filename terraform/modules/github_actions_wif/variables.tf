variable "project" {
  description = "GCP project id"
  type        = string
}

variable "name" {
  description = "Prefix of the service account ids (<name>-deployer / <name>-planner, at most 30 characters in total)"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in the form 'owner/repo' that is allowed to deploy via Workload Identity Federation"
  type        = string
}

variable "deploy_branch" {
  description = "Branch whose GitHub Actions runs may impersonate the deployer; pull requests into it may impersonate the planner"
  type        = string
  default     = "main"
}

variable "deployer_roles" {
  description = "Project roles granted to the deployer service account"
  type        = list(string)
}

variable "planner_roles" {
  description = "Project roles granted to the read-only planner service account used by pull requests"
  type        = list(string)
}

variable "tf_state_bucket" {
  description = "Name of the GCS bucket holding the environment's tfstate; the planner service account gets read-only access to it"
  type        = string
}
