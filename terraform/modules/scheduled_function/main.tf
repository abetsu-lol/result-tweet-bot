// Cloud Scheduler から Pub/Sub 経由で定期的に起動される Cloud Function

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

// Cloud Functions はデプロイのたびに Cloud Build でビルドし、イメージを Artifact Registry に保存する
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

// 関数のビルドで作られるイメージの保存先。自動作成される gcf-artifacts ではなく自前のリポジトリにすることで
// 古いイメージを削除できる。イメージは 1 つ約 450MB で、ほとんどがランタイムのベースイメージ。
resource "google_artifact_registry_repository" "images" {
  project       = var.project
  location      = var.region
  repository_id = "${var.name}-images"
  format        = "DOCKER"
  description   = "Cloud Function ${var.name} のビルドイメージ"

  cleanup_policy_dry_run = false

  // KEEP は DELETE より優先される。最新のバージョンだけが残る
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

// ソースが変わるとオブジェクト名が変わり、それによって関数が再デプロイされる。
// 名前は zip ではなくソースファイルから計算する（zip のバイト列は環境によって変わりうるため）。
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
    // 置き換えの要否は `name` に含まれる内容ハッシュで決まる。zip のパスは環境によって異なり、
    // また（`source` の変更で強制される）同じ名前での置き換えは、アップロードしたばかりのオブジェクトを削除してしまう。
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
  description = "定期実行ジョブの関数"
  project     = var.project
  region      = var.region
  runtime     = var.runtime
  entry_point = var.entry_point

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

// Cloud Scheduler のサービスエージェントに Pub/Sub topic への publish を許可する
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
  description = "Pub/Sub 経由で Cloud Function を毎日起動する"
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
