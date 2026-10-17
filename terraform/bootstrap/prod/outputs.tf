// Set as the environment variable GCP_WORKLOAD_PROVIDER
output "wif_provider" {
  value = module.github_actions_wif.wif_provider
}

// Set as the environment variable GCP_SA_EMAIL
output "deployer_service_account_email" {
  value = module.github_actions_wif.deployer_service_account_email
}
