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

resource "google_storage_bucket" "function_source_bucket" {
  project                     = var.project
  name                        = "${var.service_name}-fn-src-${var.project}"
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

resource "google_storage_bucket_object" "function_zip" {
  name   = "function-${local.function_source_hash}.zip"
  bucket = google_storage_bucket.function_source_bucket.name
  source = var.source_zip_path

  lifecycle {
    create_before_destroy = true
    // The content hash in `name` is what decides replacement. The zip path differs between
    // environments and the zip bytes differ between builds, and replacing an object under the
    // same name would delete the freshly uploaded copy.
    ignore_changes = [source, detect_md5hash]
  }
}

resource "google_pubsub_topic" "daily_topic" {
  project = var.project
  name    = "${var.service_name}-topic"
}

data "google_project" "project" {
  project_id = var.project
}

resource "google_cloudfunctions_function" "daily_function" {
  name        = var.service_name
  description = "Daily job function"
  project     = var.project
  region      = var.region
  runtime     = var.runtime
  entry_point = var.entry_point

  source_archive_bucket = google_storage_bucket.function_source_bucket.name
  source_archive_object = google_storage_bucket_object.function_zip.name

  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource   = google_pubsub_topic.daily_topic.name
  }
  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.storage,
    google_storage_bucket.function_source_bucket,
    google_storage_bucket_object.function_zip,
  ]
}

// Allow Cloud Scheduler service agent to publish to Pub/Sub topic
resource "google_pubsub_topic_iam_member" "scheduler_publisher" {
  project = var.project
  topic   = google_pubsub_topic.daily_topic.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
  depends_on = [
    google_project_service.scheduler,
    google_pubsub_topic.daily_topic,
  ]
}

resource "google_cloud_scheduler_job" "daily_trigger" {
  project     = var.project
  region      = var.region
  name        = "${var.service_name}-scheduler"
  description = "Trigger Cloud Function daily via Pub/Sub"
  schedule    = var.schedule
  time_zone   = var.time_zone

  pubsub_target {
    topic_name = google_pubsub_topic.daily_topic.id
    data       = base64encode(jsonencode({}))
  }
  depends_on = [
    google_project_service.scheduler,
    google_pubsub_topic.daily_topic,
  ]
}
