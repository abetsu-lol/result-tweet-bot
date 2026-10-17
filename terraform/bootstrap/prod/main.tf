// CI の前提となるリソース。プロジェクトの管理者がローカルから apply する（初回とまれな変更のみ）。
// Workload Identity Federation と、GitHub Actions が借用するデプロイ用サービスアカウントを含む。
// CI が自身の認証情報やプロジェクトの IAM を変更できないよう、CI が apply する環境からは分けている。
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
    // editor では IAM ポリシーを設定できない。Cloud Scheduler 用の Pub/Sub topic への権限付与に必要
    "roles/pubsub.admin",
  ]
}

// 関数のビルドに必要なプロジェクトの IAM。デプロイ用 SA には IAM の権限がないため CI では付与できない
module "function_build_iam" {
  source = "../../modules/function_build_iam"

  project = var.project
}
