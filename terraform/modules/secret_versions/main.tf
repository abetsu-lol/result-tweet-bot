// Values of the Secret Manager secrets created by modules/function_runtime (bootstrap/prod).
// Values are write-only: they are sent to Secret Manager but never stored in plan or state.
// Terraform cannot compare write-only values, so a new version is added only when the
// version number for that secret changes; bump it whenever the value is changed.

resource "google_secret_manager_secret_version" "this" {
  for_each = var.versions

  secret                 = "projects/${var.project}/secrets/${each.key}"
  secret_data_wo         = var.values[each.key]
  secret_data_wo_version = each.value

  // Add the new version before destroying the old one, so a version is always available
  lifecycle {
    create_before_destroy = true
  }
}
