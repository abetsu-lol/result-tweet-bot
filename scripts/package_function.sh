#!/usr/bin/env bash
set -euo pipefail

# Zips cloud_function/ into build/function.zip, which terraform/function.tf uploads via var.function_zip_path.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FUNCTION_DIR="$ROOT_DIR/cloud_function"
OUT_ZIP="$ROOT_DIR/build/function.zip"

mkdir -p "$(dirname "$OUT_ZIP")"
rm -f "$OUT_ZIP"
pushd "$FUNCTION_DIR" >/dev/null
zip -r "$OUT_ZIP" . -x "*.pyc" "__pycache__/*"
popd >/dev/null

echo "Packaged $FUNCTION_DIR to $OUT_ZIP"
