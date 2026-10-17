# PowerShell bootstrap script
# Usage: .\scripts\bootstrap.ps1
Param()

# Get project from gcloud
$project = (& gcloud config get-value project --quiet) -replace "\r|\n",""
if (-not $project) {
  Write-Error "gcloud project not set. Run: gcloud init or gcloud config set project YOUR_PROJECT_ID"
  exit 1
}

$bucket = $env:TFSTATE_BUCKET
if (-not $bucket) { $bucket = "terraform-state-$project" }
$tfvarsDir = "terraform/bootstrap"
$tfvarsFile = Join-Path $tfvarsDir "terraform.tfvars"

@"
project = "$project"
backend_bucket = "$bucket"
region = "asia-northeast1"
"@ | Out-File -FilePath $tfvarsFile -Encoding utf8

Write-Host "Created $tfvarsFile with project=$project backend_bucket=$bucket"

Push-Location $tfvarsDir
terraform init
terraform apply -auto-approve
Pop-Location

$backendFile = Join-Path (Get-Location) "terraform/backend.hcl"
[IO.File]::WriteAllText($backendFile, "bucket = `"$bucket`"`nprefix = `"terraform/state`"`n")

Write-Host "Bootstrap complete. Created $backendFile. Next, run: terraform init -backend-config=backend.hcl in the terraform/ directory."