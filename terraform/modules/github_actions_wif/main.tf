// Workload Identity Federation that lets GitHub Actions runs of one repository/branch
// impersonate a deployer service account

data "google_project" "project" {
  project_id = var.project
}

// Enable required APIs for Workload Identity Federation
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

// APIs that Terraform itself calls when the deployer runs it. Requests made with a service account
// are attributed to its own project, so these must be enabled here (user credentials do not need them).
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
  description               = "Pool for GitHub Actions OIDC tokens"
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
    "attribute.event_name" = "assertion.event_name"
  }

  // Only tokens issued for this repository are accepted. Which service account each run may
  // impersonate is decided by the bindings below (by branch or by event).
  attribute_condition = "assertion.repository == '${var.github_repository}'"
}

// Service account that GitHub Actions impersonates to deploy
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

// Lets only runs on the deploy branch impersonate the deployer
resource "google_service_account_iam_member" "deploy_github_actions" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"

  member = format("principalSet://iam.googleapis.com/projects/%s/locations/global/workloadIdentityPools/%s/attribute.ref/refs/heads/%s",
    data.google_project.project.number,
    google_iam_workload_identity_pool.github.workload_identity_pool_id,
    var.deploy_branch
  )

  depends_on = [google_iam_workload_identity_pool_provider.github]
}

// service account for Github Actions contain teraffrom code validation and python code test
resource "google_service_account" "planner" {
  project      = var.project
  account_id   = "${var.name}-planner"
  display_name = "Validater for ${var.github_repository} (GitHub Actions via WIF)"
}

// Lets the planner read the environment state. It runs plan with -lock=false, so it needs no write access.
resource "google_storage_bucket_iam_member" "planner_state_reader" {
  bucket = var.tf_state_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.planner.email}"
}

resource "google_project_iam_member" "planner_roles" {
  for_each = toset(var.planner_roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.planner.email}"
}

resource "google_service_account_iam_member" "plan_github_actions" {
  service_account_id = google_service_account.planner.name
  role               = "roles/iam.workloadIdentityUser"
  // Matched by event rather than by subject, whose format depends on the repository's OIDC settings
  member = format("principalSet://iam.googleapis.com/projects/%s/locations/global/workloadIdentityPools/%s/attribute.event_name/pull_request",
    data.google_project.project.number,
    google_iam_workload_identity_pool.github.workload_identity_pool_id
  )

  depends_on = [google_iam_workload_identity_pool_provider.github]
}
