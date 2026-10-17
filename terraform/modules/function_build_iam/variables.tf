variable "project" {
  description = "GCP project id"
  type        = string
}

variable "roles" {
  description = "Project roles granted to the Cloud Build service account (the Compute Engine default service account)"
  type        = list(string)
  default     = ["roles/run.builder"]
}
