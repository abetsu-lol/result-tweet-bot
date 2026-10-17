output "scheduler_name" {
  value = google_cloud_scheduler_job.daily_trigger.name
}

output "wif_pool" {
  value = google_iam_workload_identity_pool.github_pool.name
}

// Set as the GitHub secret GCP_WORKLOAD_PROVIDER
output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github_provider.name
}

// Set as the GitHub secret GCP_SA_EMAIL
output "github_actions_sa_email" {
  value = google_service_account.github_actions_sa.email
}
