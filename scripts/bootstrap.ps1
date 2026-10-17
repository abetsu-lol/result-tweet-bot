# Usage: .\scripts\bootstrap.ps1 [-Project <id>] [-Region <region>] [-Bucket <name>]
# Creates (or updates the settings of) the GCS bucket that holds Terraform state, then writes terraform/backend.hcl.
# Project defaults to the current gcloud project, Region to asia-northeast1,
# Bucket to $env:TFSTATE_BUCKET or terraform-state-<Project>.
# Safe to re-run: existing state objects are never touched.
Param(
  [string]$Project,
  [string]$Region = "asia-northeast1",
  [string]$Bucket = $env:TFSTATE_BUCKET
)

$root = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")
if (-not $Project) { $Project = ((& gcloud config get-value project --quiet 2>$null) | Out-String).Trim() }
if (-not $Project) {
  Write-Error "Project not specified. Run: .\scripts\bootstrap.ps1 -Project YOUR_PROJECT_ID (or gcloud config set project YOUR_PROJECT_ID)"
  exit 1
}
if (-not $Bucket) { $Bucket = "terraform-state-$Project" }

& gcloud storage buckets describe "gs://$Bucket" --project=$Project *> $null
if ($LASTEXITCODE -eq 0) {
  Write-Host "Bucket gs://$Bucket already exists; updating its settings."
} else {
  & gcloud storage buckets create "gs://$Bucket" --project=$Project --location=$Region `
    --uniform-bucket-level-access --public-access-prevention
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Keep previous versions of the state so it can be restored; only noncurrent versions are ever deleted.
$lifecycleFile = New-TemporaryFile
try {
  [IO.File]::WriteAllText($lifecycleFile.FullName, @'
{"rule": [
  {"action": {"type": "Delete"}, "condition": {"isLive": false, "numNewerVersions": 5}},
  {"action": {"type": "Delete"}, "condition": {"isLive": false, "daysSinceNoncurrentTime": 90}}
]}
'@)
  & gcloud storage buckets update "gs://$Bucket" --project=$Project `
    --versioning --uniform-bucket-level-access --public-access-prevention --lifecycle-file="$($lifecycleFile.FullName)"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Remove-Item $lifecycleFile.FullName -ErrorAction SilentlyContinue
}

$backendFile = Join-Path $root "terraform\backend.hcl"
[IO.File]::WriteAllText($backendFile, "bucket = `"$Bucket`"`nprefix = `"terraform/state`"`n")

Write-Host "Bootstrap complete. Wrote $backendFile. Next: cd terraform; terraform init -backend-config=backend.hcl"
