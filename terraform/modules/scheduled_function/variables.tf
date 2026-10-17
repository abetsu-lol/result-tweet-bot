variable "project" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region for the function, its source bucket and the scheduler job"
  type        = string
}

variable "service_name" {
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
  description = "Cloud Functions runtime"
  type        = string
  default     = "python310"
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
