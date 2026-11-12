#!/usr/bin/env bash
set -euo pipefail

# Zips cloud_function/ into build/function.zip, which terraform/environments/prod uploads.
# The zip is reproducible (fixed timestamps, permissions and order): identical sources give an
# identical zip, so Terraform does not re-upload the object on every run.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FUNCTION_DIR="$ROOT_DIR/cloud_function"
OUT_ZIP="$ROOT_DIR/build/function.zip"

PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
  echo "python is required" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_ZIP")"
rm -f "$OUT_ZIP"
"$PYTHON" - "$FUNCTION_DIR" "$OUT_ZIP" <<'PY'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(src):
        # test/ directories are for local runs only and are not deployed
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", "test"))
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            path = os.path.join(dirpath, name)
            info = zipfile.ZipInfo(os.path.relpath(path, src).replace(os.sep, "/"), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(path, "rb") as f:
                zf.writestr(info, f.read())
PY

echo "Packaged $FUNCTION_DIR to $OUT_ZIP"
