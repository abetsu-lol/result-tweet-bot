terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  // Bucket and prefix are supplied at init time so that each deployment can use its own state bucket.
  // CI passes them as -backend-config flags from the TF_STATE_BUCKET repository variable.
  backend "gcs" {}
}

provider "google" {
  project = var.project
  region  = var.region
}

locals {
  service_name = "daily-python-job"
  repo_root    = "${path.module}/../../.."
}

module "scheduled_function" {
  source = "../../modules/scheduled_function"

  project         = var.project
  region          = var.region
  service_name    = local.service_name
  source_dir      = "${local.repo_root}/cloud_function"
  source_zip_path = "${local.repo_root}/build/function.zip"
  schedule        = "0 3 * * *" // daily at 03:00
  time_zone       = "Asia/Tokyo"
}

module "github_actions_wif" {
  source = "../../modules/github_actions_wif"

  project           = var.project
  service_name      = local.service_name
  github_repository = var.github_repository
  deploy_branch     = "main"
  ci_roles = [
    "roles/editor",
    "roles/iam.securityAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
  ]
}
