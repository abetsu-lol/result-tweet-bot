variable "project" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region for the function, its source bucket and the scheduler job"
  type        = string
}

variable "name" {
  description = "Name of the function; also used as the prefix of related resources"
  type        = string
}

variable "source_dir" {
  description = "Function source directory; must match what was packaged into source_zip_path"
  type        = string
}

variable "source_zip_path" {
  description = "Path to the function source zip built by scripts/package_function.sh"
  type        = string
}

variable "runtime" {
  description = "Cloud Functions runtime (1st gen)"
  type        = string
  default     = "python312"
}

variable "image_keep_count" {
  description = "Number of most recent function images kept in Artifact Registry; older ones are deleted"
  type        = number
  default     = 2
}

variable "entry_point" {
  description = "Name of the function in the source to invoke"
  type        = string
  default     = "daily_job"
}

variable "schedule" {
  description = "Cron schedule of the Cloud Scheduler job"
  type        = string
  default     = "0 3 * * *"
}

variable "time_zone" {
  description = "Time zone of the schedule"
  type        = string
  default     = "Asia/Tokyo"
}

variable "service_account_email" {
  description = "Service account the function runs as; null uses the App Engine default service account"
  type        = string
  default     = null
}

variable "memory_mb" {
  description = "Memory available to the function in MB"
  type        = number
  default     = 256
}

variable "timeout_seconds" {
  description = "Maximum execution time of one invocation in seconds (at most 540 for 1st gen)"
  type        = number
  default     = 60
}

variable "environment_variables" {
  description = "Environment variables of the function. Secrets go to Secret Manager and are read at runtime, not here"
  type        = map(string)
  default     = {}
}
