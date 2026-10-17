// Bucket and prefix are supplied at init time so that each deployment can use its own state bucket.
// CI passes them as -backend-config flags from the TF_STATE_BUCKET repository variable.
terraform {
  backend "gcs" {}
}
