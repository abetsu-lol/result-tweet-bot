output "function_name" {
  value = google_cloudfunctions_function.this.name
}

output "scheduler_name" {
  value = google_cloud_scheduler_job.daily.name
}
