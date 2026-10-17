output "function_name" {
  value = google_cloudfunctions_function.daily_function.name
}

output "scheduler_name" {
  value = google_cloud_scheduler_job.daily_trigger.name
}
