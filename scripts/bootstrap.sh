#!/usr/bin/env bash
set -euo pipefail

# 使い方: ./scripts/bootstrap.sh [PROJECT] [REGION]
# Terraform の state を保存する GCS バケットを作成する（既にあれば設定を更新する）。
# PROJECT の既定値は gcloud の現在のプロジェクト、REGION の既定値は asia-northeast1。
# バケット名の既定値は terraform-state-<PROJECT>。TFSTATE_BUCKET で変更できる。
# 何度実行しても安全（既存の state オブジェクトには触れない）。

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

# 復元できるよう state の過去の版を残す。自動削除の対象は古い版（noncurrent）のみ。
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

echo "Bootstrap complete. Set the GitHub repository variable TF_STATE_BUCKET=${BUCKET}"
