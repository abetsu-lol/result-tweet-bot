// Workload Identity Federation that lets GitHub Actions runs of one repository/branch
// impersonate a service account with the roles needed to run terraform apply

data "google_project" "project" {
  project_id = var.project
}

// Enable required APIs for Workload Identity Federation and Terraform-managed resources
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

resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = var.project
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "gha-wif-pool"
  description               = "Pool for GitHub Actions OIDC tokens"
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = var.project
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
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

  // Only tokens issued for this repository's deploy branch are accepted, so forks and
  // other branches (including pull requests) can never obtain credentials here.
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/${var.deploy_branch}'"

  depends_on = [
    google_iam_workload_identity_pool.github_pool,
  ]
}

// Service account for GitHub Actions to impersonate
resource "google_service_account" "github_actions_sa" {
  project      = var.project
  account_id   = "${var.service_name}-gha-sa"
  display_name = "Service account for GitHub Actions (WIF)"
}

// Roles the CI service account needs to run `terraform apply` for this configuration
resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset(var.ci_roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"
}

// Grant Workload Identity User to the GitHub repository principal for the SA
resource "google_service_account_iam_member" "github_binding" {
  count              = var.create_github_binding ? 1 : 0
  service_account_id = google_service_account.github_actions_sa.name
  role               = "roles/iam.workloadIdentityUser"

  member = format("principalSet://iam.googleapis.com/projects/%s/locations/global/workloadIdentityPools/%s/attribute.repository/%s",
    data.google_project.project.number,
    google_iam_workload_identity_pool.github_pool.workload_identity_pool_id,
    var.github_repository
  )

  depends_on = [
    google_iam_workload_identity_pool_provider.github_provider,
    google_service_account.github_actions_sa,
  ]
}
