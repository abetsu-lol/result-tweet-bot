#!/usr/bin/env bash
set -euo pipefail

# Validates the secret files and registers them as GitHub secrets of the "prod" environment.
# CI writes them to Secret Manager on the next apply once their version numbers are bumped in
# terraform/environments/prod/main.tf. Values are never printed; JSON is minified to one line.
#
# Usage:
#   ./scripts/set_secrets.sh [--dir DIR] --check            validate only
#   ./scripts/set_secrets.sh [--dir DIR]                    validate and register all secrets
#   ./scripts/set_secrets.sh [--dir DIR] NAME               validate and register one secret
#   ./scripts/set_secrets.sh [--dir DIR] --direct NAME      also add it to Secret Manager right away
#                                                           (for the daily Development key rotation)
# NAME: RIOT_API_KEY | X_APP_CREDENTIALS | ACCOUNTS
# DIR defaults to ~/result-tweet-bot-secrets (copy secrets.example/ there and fill it in).
# Keep DIR outside the repository: the files contain credentials.

DIR="$HOME/result-tweet-bot-secrets"
ENVIRONMENT="prod"
CHECK_ONLY=false
DIRECT=false
TARGETS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --check) CHECK_ONLY=true; shift ;;
    --direct) DIRECT=true; shift ;;
    *) TARGETS+=("$1"); shift ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=(RIOT_API_KEY X_APP_CREDENTIALS ACCOUNTS)
if $DIRECT && [ ${#TARGETS[@]} -ne 1 ]; then
  echo "--direct takes exactly one NAME" >&2
  exit 1
fi

PYTHON="$(command -v python3 || command -v python)"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

declare -A SECRET_ID=([RIOT_API_KEY]=riot-api-key [X_APP_CREDENTIALS]=x-app-credentials [ACCOUNTS]=accounts)

# Prints the value to register on stdout; errors (without values) go to stderr.
# -X utf8: on Windows, Python would otherwise write Shift_JIS and corrupt non-ASCII values.
normalize() {
  "$PYTHON" -X utf8 - "$1" "$DIR" <<'PY'
import json, re, sys
name, d = sys.argv[1], sys.argv[2]
PLATFORMS = {"br1", "eun1", "euw1", "jp1", "kr", "la1", "la2", "me1", "na1", "oc1",
             "ph2", "ru", "sg2", "th2", "tr1", "tw2", "vn2"}
errors = []

def need(obj, key, where):
    v = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(v, str) or not v.strip():
        errors.append(f"{where}.{key} is missing")
        return ""
    if v.strip().startswith("<"):
        errors.append(f"{where}.{key} is still the template placeholder")
    return v.strip()

if name == "RIOT_API_KEY":
    v = open(f"{d}/RIOT_API_KEY.txt", encoding="utf-8").read().strip()
    if v.startswith("<"):
        errors.append("RIOT_API_KEY is still the template placeholder")
    elif not v.startswith("RGAPI-"):
        errors.append("RIOT_API_KEY does not start with RGAPI-")
    out = v
elif name == "X_APP_CREDENTIALS":
    o = json.load(open(f"{d}/X_APP_CREDENTIALS.json", encoding="utf-8"))
    for k in ("consumer_key", "consumer_secret"):
        need(o, k, "X_APP_CREDENTIALS")
    out = json.dumps(o, ensure_ascii=False, separators=(",", ":"))
elif name == "ACCOUNTS":
    a = json.load(open(f"{d}/ACCOUNTS.json", encoding="utf-8"))
    if not isinstance(a, list) or not a:
        errors.append("ACCOUNTS must be a non-empty array")
        a = []
    ids = set()
    for i, acc in enumerate(a):
        w = f"ACCOUNTS[{i}]"
        aid = need(acc, "id", w)
        if aid and not re.fullmatch(r"[a-z0-9-]+", aid):
            errors.append(f"{w}.id must contain only a-z, 0-9 and -")
        if aid in ids:
            errors.append(f"{w}.id is duplicated")
        ids.add(aid)
        riot, x = acc.get("riot", {}), acc.get("x", {})
        need(riot, "game_name", f"{w}.riot")
        if need(riot, "tag_line", f"{w}.riot").startswith("#"):
            errors.append(f"{w}.riot.tag_line must not start with #")
        p = need(riot, "platform", f"{w}.riot")
        if p and p not in PLATFORMS:
            errors.append(f"{w}.riot.platform is unknown")
        need(x, "access_token", f"{w}.x")
        need(x, "access_token_secret", f"{w}.x")
        rp = x.get("root_post_id")
        if not isinstance(rp, str):
            errors.append(f"{w}.x.root_post_id must be a string (quoted)")
        elif not rp.isdigit():
            errors.append(f"{w}.x.root_post_id is not a numeric post id")
    out = json.dumps(a, ensure_ascii=False, separators=(",", ":"))
else:
    errors.append(f"unknown secret name: {name}")
    out = ""

if errors:
    print("\n".join(f"  NG: {e}" for e in sorted(set(errors))), file=sys.stderr)
    sys.exit(1)
sys.stdout.write(out)
PY
}

failed=false
registered=()
for name in "${TARGETS[@]}"; do
  if ! value="$(normalize "$name")"; then
    echo "NG: $name (fix the items above)"
    failed=true
    continue
  fi
  if $CHECK_ONLY; then
    echo "OK: $name"
    continue
  fi
  printf '%s' "$value" | gh secret set "$name" -R "$REPO" --env "$ENVIRONMENT" >/dev/null
  echo "Registered GitHub secret: $name (environment: $ENVIRONMENT)"
  if $DIRECT; then
    project="$(gh variable get GCP_PROJECT_ID -R "$REPO" --env "$ENVIRONMENT")"
    printf '%s' "$value" | gcloud secrets versions add "${SECRET_ID[$name]}" --project "$project" --data-file=- >/dev/null
    echo "Added a Secret Manager version: ${SECRET_ID[$name]} (takes effect on the next run)"
  else
    registered+=("${SECRET_ID[$name]}")
  fi
done
unset value

if [ ${#registered[@]} -gt 0 ]; then
  echo
  echo "Next: bump the version of ${registered[*]} in terraform/environments/prod/main.tf"
  echo "      (module \"secret_versions\") and merge it; the deploy writes the new value."
fi
$failed && exit 1 || true
