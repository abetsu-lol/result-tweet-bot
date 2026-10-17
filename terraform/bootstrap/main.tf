provider "google" {
  project = var.project
  region  = var.region
}

resource "google_storage_bucket" "tfstate_bucket" {
  name     = var.backend_bucket
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 365
    }
  }
}
