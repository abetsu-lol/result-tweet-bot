// Set as the environment variable GCP_WORKLOAD_PROVIDER
output "wif_provider" {
  value = module.github_actions_wif.wif_provider
}

// Set as the environment variable GCP_SA_EMAIL
output "deployer_service_account_email" {
  value = module.github_actions_wif.deployer_service_account_email
}


output "runtime_service_account_email" {
  value = module.function_runtime.runtime_service_account_email
}

output "data_bucket_name" {
  value = module.function_runtime.data_bucket_name
}

// Set as the repository variable GCP_PLAN_SA_EMAIL
output "planner_service_account_email" {
  value = module.github_actions_wif.planner_service_account_email
}
