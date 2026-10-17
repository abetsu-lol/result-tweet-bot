GCS backend bootstrap and usage

Goal: store Terraform state in a GCS bucket. Because Terraform requires the bucket to exist before configuring the `gcs` backend, follow these steps:

1) Create the bucket (bootstrap step)

```bash
./scripts/bootstrap.sh      # or .\scripts\bootstrap.ps1
```

The script reads the current `gcloud` project, writes `terraform/bootstrap/terraform.tfvars`, runs `terraform apply` in `terraform/bootstrap/`
to create the bucket (`terraform-state-<project>` unless `TFSTATE_BUCKET` is set), and writes `terraform/backend.hcl`.

You can also create the bucket manually via `gcloud storage buckets create gs://your-tfstate-bucket --location=REGION` and write
`terraform/backend.hcl` yourself (see `backend.hcl.example`).

2) Initialize main terraform to use the GCS backend

```bash
cd terraform
terraform init -backend-config=backend.hcl
```

`backend.tf` intentionally leaves `bucket`/`prefix` empty so that every deployment can use its own bucket.
In CI they are passed as `-backend-config` flags from the `TF_STATE_BUCKET` repository variable.

Notes:
- `terraform/bootstrap/terraform.tfstate` is local state for the bucket itself. It is not committed; keep it safe.
- The CI service account is granted `roles/editor`, which includes access to the state bucket.
