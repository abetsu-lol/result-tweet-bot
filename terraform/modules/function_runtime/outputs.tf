output "runtime_service_account_email" {
  value = google_service_account.runtime.email
}

output "data_bucket_name" {
  value = google_storage_bucket.data.name
}

output "secret_ids" {
  value = [for s in google_secret_manager_secret.this : s.secret_id]
}
