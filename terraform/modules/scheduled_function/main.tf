// Pub/Sub-triggered Cloud Function invoked on a schedule by Cloud Scheduler

resource "google_project_service" "cloudfunctions" {
  project = var.project
  service = "cloudfunctions.googleapis.com"
}

resource "google_project_service" "pubsub" {
  project = var.project
  service = "pubsub.googleapis.com"
}

resource "google_project_service" "scheduler" {
  project = var.project
  service = "cloudscheduler.googleapis.com"
}

resource "google_project_service" "storage" {
  project = var.project
  service = "storage.googleapis.com"
}

// Cloud Functions builds each deployment with Cloud Build and stores the image in Artifact Registry
resource "google_project_service" "cloudbuild" {
  project            = var.project
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  project            = var.project
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

// Images built for the function. Using our own repository (instead of the auto-created gcf-artifacts)
// lets old images be cleaned up; each image is ~450MB, mostly the runtime base image.
resource "google_artifact_registry_repository" "images" {
  project       = var.project
  location      = var.region
  repository_id = "${var.name}-images"
  format        = "DOCKER"
  description   = "Images built for the ${var.name} Cloud Function"

  cleanup_policy_dry_run = false

  // KEEP takes precedence over DELETE: only the most recent versions survive
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = var.image_keep_count
    }
  }

  cleanup_policies {
    id     = "delete-others"
    action = "DELETE"
    condition {
      tag_state = "ANY"
    }
  }

  depends_on = [google_project_service.artifactregistry]
}

resource "google_storage_bucket" "source" {
  project                     = var.project
  name                        = "${var.name}-src-${var.project}"
  location                    = var.region
  uniform_bucket_level_access = true
}

// The object name changes whenever the source changes, which is what makes the function redeploy.
// It is derived from the source files rather than the zip, whose bytes vary between builds.
locals {
  function_source_files = sort([
    for f in fileset(var.source_dir, "**") : f
    if !strcontains(f, "__pycache__") && !endswith(f, ".pyc")
  ])
  function_source_hash = sha1(join("", [
    for f in local.function_source_files : "${f}:${filesha1("${var.source_dir}/${f}")}"
  ]))
}

resource "google_storage_bucket_object" "source" {
  name   = "function-${local.function_source_hash}.zip"
  bucket = google_storage_bucket.source.name
  source = var.source_zip_path

  lifecycle {
    create_before_destroy = true
    // The content hash in `name` is what decides replacement. The zip path differs between
    // environments, and replacing the object under the same name (which a `source` change would
    // force) would delete the freshly uploaded copy.
    ignore_changes = [source]
  }
}

resource "google_pubsub_topic" "trigger" {
  project = var.project
  name    = "${var.name}-trigger"
}

data "google_project" "project" {
  project_id = var.project
}

resource "google_cloudfunctions_function" "this" {
  name        = var.name
  description = "Scheduled job function"
  project     = var.project
  region      = var.region
  runtime     = var.runtime
  entry_point = var.entry_point

  service_account_email = var.service_account_email
  available_memory_mb   = var.memory_mb
  timeout               = var.timeout_seconds
  environment_variables = var.environment_variables

  docker_registry   = "ARTIFACT_REGISTRY"
  docker_repository = google_artifact_registry_repository.images.id

  source_archive_bucket = google_storage_bucket.source.name
  source_archive_object = google_storage_bucket_object.source.name

  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource   = google_pubsub_topic.trigger.name
  }
  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.cloudbuild,
    google_project_service.artifactregistry,
    google_project_service.storage,
    google_storage_bucket.source,
    google_storage_bucket_object.source,
  ]
}

// Allow Cloud Scheduler service agent to publish to Pub/Sub topic
resource "google_pubsub_topic_iam_member" "scheduler_publisher" {
  project = var.project
  topic   = google_pubsub_topic.trigger.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
  depends_on = [
    google_project_service.scheduler,
    google_pubsub_topic.trigger,
  ]
}

resource "google_cloud_scheduler_job" "daily" {
  project     = var.project
  region      = var.region
  name        = "${var.name}-daily"
  description = "Trigger Cloud Function daily via Pub/Sub"
  schedule    = var.schedule
  time_zone   = var.time_zone

  pubsub_target {
    topic_name = google_pubsub_topic.trigger.id
    data       = base64encode(jsonencode({}))
  }
  depends_on = [
    google_project_service.scheduler,
    google_pubsub_topic.trigger,
  ]
}
