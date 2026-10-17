// Terraform skeleton for Google Cloud Run (placeholders)
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

// TODO: Add backend configuration (e.g., GCS) and resources
