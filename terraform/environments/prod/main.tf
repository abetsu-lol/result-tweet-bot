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
}

module "scheduled_function" {
  source = "../../modules/scheduled_function"

  project         = var.project
  region          = var.region
  name            = local.name
  source_dir      = "${local.repo_root}/cloud_function"
  source_zip_path = "${local.repo_root}/build/function.zip"
  schedule        = "0 3 * * *" // daily at 03:00
  time_zone       = "Asia/Tokyo"
}
