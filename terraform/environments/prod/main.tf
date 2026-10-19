terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  // Bucket and prefix are supplied at init time so that each deployment can use its own state bucket.
  // CI passes them as -backend-config flags from the TF_STATE_BUCKET environment variable.
  backend "gcs" {}
}

provider "google" {
  project = var.project
  region  = var.region
}

locals {
  name      = "result-tweet-bot"
  repo_root = "${path.module}/../../.."

  // Created by modules/function_runtime in terraform/bootstrap/prod (same naming)
  runtime_service_account_email = "${local.name}-runtime@${var.project}.iam.gserviceaccount.com"
  data_bucket                   = "${local.name}-data-${var.project}"
}

module "scheduled_function" {
  source = "../../modules/scheduled_function"

  project         = var.project
  region          = var.region
  name            = local.name
  source_dir      = "${local.repo_root}/cloud_function"
  source_zip_path = "${local.repo_root}/build/function.zip"
  // Collects the 12:00-12:00 (JST) day that has just ended, and posts it when the post schedule says so
  schedule  = "5 12 * * *"
  time_zone = "Asia/Tokyo"

  service_account_email = local.runtime_service_account_email
  memory_mb             = 512
  timeout_seconds       = 300

  environment_variables = {
    DATA_BUCKET = local.data_bucket
    // Secret Manager secret names (values are read at runtime so that rotated keys apply immediately)
    SECRET_RIOT_API_KEY      = "projects/${var.project}/secrets/riot-api-key"
    SECRET_X_APP_CREDENTIALS = "projects/${var.project}/secrets/x-app-credentials"
    SECRET_ACCOUNTS          = "projects/${var.project}/secrets/accounts"
    // Posting: daily | weekly:<MON..SUN>, image | text, per_game | summary
    POST_SCHEDULE = "daily"
    POST_FORMAT   = "image"
    POST_LAYOUT   = "per_game"
    // Keep true until going live: collect and store, but do not post
    DRY_RUN = "true"
  }
}
