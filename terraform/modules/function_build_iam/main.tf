// Cloud Functions のデプロイ時に Cloud Build がビルドで使うサービスアカウントへの権限。
// 新しいプロジェクトでは Compute Engine のデフォルト SA でビルドされるが、既定ではロールが付いていない。

data "google_project" "project" {
  project_id = var.project
}

resource "google_project_iam_member" "build" {
  for_each = toset(var.roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}
