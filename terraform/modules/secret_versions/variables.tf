variable "project" {
  description = "GCP project id"
  type        = string
}

variable "versions" {
  description = "Version number per secret id; bump it to write the current value as a new secret version"
  type        = map(number)
}

variable "values" {
  description = "Value per secret id (same keys as versions)"
  type        = map(string)
  ephemeral   = true
  sensitive   = true
}
