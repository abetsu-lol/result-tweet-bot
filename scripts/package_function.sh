#!/usr/bin/env bash
set -euo pipefail

# Zips cloud_function/ into build/function.zip, which terraform/function.tf uploads via var.function_zip_path.
# Uses `zip` when available, otherwise Python (e.g. Git Bash on Windows has no zip).
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FUNCTION_DIR="$ROOT_DIR/cloud_function"
OUT_ZIP="$ROOT_DIR/build/function.zip"

mkdir -p "$(dirname "$OUT_ZIP")"
rm -f "$OUT_ZIP"

if command -v zip >/dev/null 2>&1; then
  pushd "$FUNCTION_DIR" >/dev/null
  zip -r "$OUT_ZIP" . -x "*.pyc" "*__pycache__/*"
  popd >/dev/null
else
  PYTHON="$(command -v python3 || command -v python || true)"
  if [ -z "$PYTHON" ]; then
    echo "Neither zip nor python is available" >&2
    exit 1
  fi
  "$PYTHON" - "$FUNCTION_DIR" "$OUT_ZIP" <<'PY'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            if not name.endswith(".pyc"):
                path = os.path.join(dirpath, name)
                zf.write(path, os.path.relpath(path, src).replace(os.sep, "/"))
PY
fi

echo "Packaged $FUNCTION_DIR to $OUT_ZIP"
