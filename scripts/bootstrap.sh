#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/bootstrap.sh
# This script uses gcloud to get the current project and creates terraform/bootstrap/terraform.tfvars
# then runs terraform init/apply non-interactively to create the GCS backend bucket.

PROJECT=$(gcloud config get-value project --quiet || true)
if [ -z "$PROJECT" ]; then
  echo "gcloud project not set. Run: gcloud init or gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

BUCKET=${TFSTATE_BUCKET:-"terraform-state-${PROJECT}"}
TFVARS_DIR="terraform/bootstrap"
TFVARS_FILE="$TFVARS_DIR/terraform.tfvars"

cat > "$TFVARS_FILE" <<EOF
project = "${PROJECT}"
backend_bucket = "${BUCKET}"
region = "asia-northeast1"
EOF

echo "Created $TFVARS_FILE with project=${PROJECT} backend_bucket=${BUCKET}"

pushd "$TFVARS_DIR" >/dev/null
terraform init
terraform apply -auto-approve
popd >/dev/null

BACKEND_FILE="terraform/backend.hcl"
cat > "$BACKEND_FILE" <<EOF
bucket = "${BUCKET}"
prefix = "terraform/state"
EOF

echo "Bootstrap complete. Created $BACKEND_FILE. Next, run: terraform init -backend-config=backend.hcl in the terraform/ directory."