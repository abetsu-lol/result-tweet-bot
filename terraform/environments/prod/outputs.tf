output "scheduler_name" {
  value = module.scheduled_function.scheduler_name
}

output "wif_pool" {
  value = module.github_actions_wif.wif_pool
}

// Set as the GitHub secret GCP_WORKLOAD_PROVIDER
output "wif_provider" {
  value = module.github_actions_wif.wif_provider
}

// Set as the GitHub secret GCP_SA_EMAIL
output "github_actions_sa_email" {
  value = module.github_actions_wif.service_account_email
}
