output "wif_pool" {
  value = google_iam_workload_identity_pool.github.name
}

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account_email" {
  value = google_service_account.deployer.email
}

output "planner_service_account_email" {
  value = google_service_account.planner.email
}
