terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  // デプロイ先ごとに別の state バケットを使えるよう、bucket と prefix は init 時に指定する。
  // CI では Environment の Variable TF_STATE_BUCKET を -backend-config で渡している。
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
  schedule        = "0 3 * * *" // 毎日 03:00
  time_zone       = "Asia/Tokyo"
}
