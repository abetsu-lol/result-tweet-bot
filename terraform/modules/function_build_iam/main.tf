// Roles for the service account that Cloud Build uses to build Cloud Functions deployments.
// New projects build with the Compute Engine default service account, which has no roles by default.

data "google_project" "project" {
  project_id = var.project
}

resource "google_project_iam_member" "build" {
  for_each = toset(var.roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}
