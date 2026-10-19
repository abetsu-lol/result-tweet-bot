// Prerequisites for CI, applied from a local machine by a project admin (initial setup and rare changes):
// Workload Identity Federation and the deployer service account that GitHub Actions impersonates.
// Kept out of the CI-applied environment so that CI cannot change its own credentials or project IAM.
terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  // terraform init -backend-config="bucket=<TF_STATE_BUCKET>" -backend-config="prefix=terraform/bootstrap"
  backend "gcs" {}
}

provider "google" {
  project = var.project
}

module "github_actions_wif" {
  source = "../../modules/github_actions_wif"

  project           = var.project
  name              = "result-tweet-bot"
  github_repository = var.github_repository
  deploy_branch     = "main"
  deployer_roles = [
    "roles/editor",
    // editor cannot set IAM policies; needed for the Pub/Sub topic binding of Cloud Scheduler
    "roles/pubsub.admin",
  ]
}

// Project IAM needed to build the function; CI cannot grant it because the deployer has no IAM rights
module "function_build_iam" {
  source = "../../modules/function_build_iam"

  project = var.project
}

// Runtime service account, secrets and data bucket of the function (IAM is involved, so not in CI)
module "function_runtime" {
  source = "../../modules/function_runtime"

  project                        = var.project
  name                           = "result-tweet-bot"
  deployer_service_account_email = module.github_actions_wif.deployer_service_account_email
}
