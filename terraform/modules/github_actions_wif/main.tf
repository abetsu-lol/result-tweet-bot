// 特定のリポジトリ・ブランチの GitHub Actions に、デプロイ用サービスアカウントの借用を許可する
// Workload Identity Federation

data "google_project" "project" {
  project_id = var.project
}

// Workload Identity Federation に必要な API を有効化する
resource "google_project_service" "iam" {
  project            = var.project
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iamcredentials" {
  project            = var.project
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "sts" {
  project            = var.project
  service            = "sts.googleapis.com"
  disable_on_destroy = false
}

// デプロイ用 SA で Terraform を実行するときに Terraform 自身が呼ぶ API。サービスアカウントによるリクエストは
// その SA のプロジェクトに帰属するため、ここで有効化しておく必要がある（ユーザーの認証情報では不要）。
resource "google_project_service" "cloudresourcemanager" {
  project            = var.project
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "serviceusage" {
  project            = var.project
  service            = "serviceusage.googleapis.com"
  disable_on_destroy = false
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "gha-wif-pool"
  description               = "GitHub Actions の OIDC トークン用のプール"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  // このリポジトリのデプロイ用ブランチで発行されたトークンだけを受け付ける。
  // fork や他のブランチ（Pull Request を含む）からは認証情報を取得できない。
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/${var.deploy_branch}'"
}

// GitHub Actions がデプロイのために借用するサービスアカウント
resource "google_service_account" "deployer" {
  project      = var.project
  account_id   = "${var.name}-deployer"
  display_name = "Deployer for ${var.github_repository} (GitHub Actions via WIF)"
}

resource "google_project_iam_member" "deployer_roles" {
  for_each = toset(var.deployer_roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

// リポジトリのワークフローにデプロイ用 SA の借用を許可する
resource "google_service_account_iam_member" "github_actions" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"

  member = format("principalSet://iam.googleapis.com/projects/%s/locations/global/workloadIdentityPools/%s/attribute.repository/%s",
    data.google_project.project.number,
    google_iam_workload_identity_pool.github.workload_identity_pool_id,
    var.github_repository
  )

  depends_on = [google_iam_workload_identity_pool_provider.github]
}
