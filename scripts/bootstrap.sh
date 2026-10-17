#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/bootstrap.sh [PROJECT] [REGION]
# Creates (or updates the settings of) the GCS bucket that holds Terraform state, then writes terraform/backend.hcl.
# PROJECT defaults to the current gcloud project, REGION to asia-northeast1.
# The bucket name defaults to terraform-state-<PROJECT>; override it with TFSTATE_BUCKET.
# Safe to re-run: existing state objects are never touched.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="${1:-$(gcloud config get-value project --quiet 2>/dev/null || true)}"
REGION="${2:-asia-northeast1}"
if [ -z "$PROJECT" ]; then
  echo "Project not specified. Run: ./scripts/bootstrap.sh YOUR_PROJECT_ID (or gcloud config set project YOUR_PROJECT_ID)" >&2
  exit 1
fi
BUCKET="${TFSTATE_BUCKET:-terraform-state-${PROJECT}}"

if gcloud storage buckets describe "gs://${BUCKET}" --project="$PROJECT" >/dev/null 2>&1; then
  echo "Bucket gs://${BUCKET} already exists; updating its settings."
else
  gcloud storage buckets create "gs://${BUCKET}" --project="$PROJECT" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi

# Keep previous versions of the state so it can be restored; only noncurrent versions are ever deleted.
LIFECYCLE_FILE="$(mktemp)"
trap 'rm -f "$LIFECYCLE_FILE"' EXIT
cat > "$LIFECYCLE_FILE" <<'JSON'
{"rule": [
  {"action": {"type": "Delete"}, "condition": {"isLive": false, "numNewerVersions": 5}},
  {"action": {"type": "Delete"}, "condition": {"isLive": false, "daysSinceNoncurrentTime": 90}}
]}
JSON
gcloud storage buckets update "gs://${BUCKET}" --project="$PROJECT" \
  --versioning --uniform-bucket-level-access --public-access-prevention --lifecycle-file="$LIFECYCLE_FILE"

BACKEND_FILE="$ROOT_DIR/terraform/backend.hcl"
cat > "$BACKEND_FILE" <<EOF
bucket = "${BUCKET}"
prefix = "terraform/state"
EOF

echo "Bootstrap complete. Wrote $BACKEND_FILE. Next: cd terraform && terraform init -backend-config=backend.hcl"
