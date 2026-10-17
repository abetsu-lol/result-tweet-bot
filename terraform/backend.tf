// Bucket and prefix are supplied at init time so that each deployment can use its own state bucket:
//   terraform init -backend-config=backend.hcl
// (see backend.hcl.example; CI passes -backend-config flags instead)
terraform {
  backend "gcs" {}
}
