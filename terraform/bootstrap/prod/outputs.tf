// Environment の Variable GCP_WORKLOAD_PROVIDER に設定する
output "wif_provider" {
  value = module.github_actions_wif.wif_provider
}

// Environment の Variable GCP_SA_EMAIL に設定する
output "deployer_service_account_email" {
  value = module.github_actions_wif.deployer_service_account_email
}
