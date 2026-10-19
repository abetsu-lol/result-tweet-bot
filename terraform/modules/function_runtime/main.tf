// What the function uses at runtime: its own service account, the secrets it reads and the bucket
// that keeps match data. All IAM lives here because the deployer cannot grant IAM.

resource "google_project_service" "secretmanager" {
  project            = var.project
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

// The function runs as this account instead of the App Engine default service account
resource "google_service_account" "runtime" {
  project      = var.project
  account_id   = "${var.name}-runtime"
  display_name = "Runtime for the ${var.name} Cloud Function"
}

// Only the containers are managed here. Values are added by CI from GitHub secrets
// (gcloud secrets versions add) so that they never appear in Terraform state.
resource "google_secret_manager_secret" "this" {
  for_each = toset(var.secret_ids)

  project   = var.project
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each = google_secret_manager_secret.this

  project   = var.project
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.runtime.member
}

// Lets CI add new versions and destroy old ones, without reading them
resource "google_secret_manager_secret_iam_member" "deployer_version_manager" {
  for_each = google_secret_manager_secret.this

  project   = var.project
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretVersionManager"
  member    = "serviceAccount:${var.deployer_service_account_email}"
}

// Match data kept indefinitely. A US region is used for the Cloud Storage free tier.
resource "google_storage_bucket" "data" {
  project  = var.project
  name     = "${var.name}-data-${var.project}"
  location = var.data_location

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  soft_delete_policy {
    retention_duration_seconds = var.data_soft_delete_days * 24 * 60 * 60
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket_iam_member" "runtime_data" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectUser"
  member = google_service_account.runtime.member
}
