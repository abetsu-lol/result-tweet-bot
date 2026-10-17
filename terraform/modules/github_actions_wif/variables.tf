variable "project" {
  description = "GCP project id"
  type        = string
}

variable "service_name" {
  description = "Prefix of the service account id"
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

variable "ci_roles" {
  description = "Project roles granted to the GitHub Actions service account so that CI can run terraform apply"
  type        = list(string)
}

variable "create_github_binding" {
  description = "If true, create the IAM binding that grants the GitHub principal access to the service account."
  type        = bool
  default     = true
}
