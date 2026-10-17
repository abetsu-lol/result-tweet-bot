variable "project" {
  description = "GCP project id"
  type        = string
}

variable "name" {
  description = "Prefix of the deployer service account id (<name>-deployer, at most 30 characters in total)"
  type        = string
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

variable "deployer_roles" {
  description = "Project roles granted to the deployer service account"
  type        = list(string)
}
