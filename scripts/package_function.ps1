# Zips cloud_function\ into build\function.zip, which terraform/function.tf uploads via var.function_zip_path.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path "$scriptDir\.."
$functionDir = Join-Path $root "cloud_function"
$outDir = Join-Path $root "build"
$outZip = Join-Path $outDir "function.zip"

New-Item -ItemType Directory -Force $outDir | Out-Null
if (Test-Path $outZip) { Remove-Item $outZip }

Push-Location $functionDir

# Collect files to include, excluding __pycache__ directories
$files = Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '\\__pycache__\\' } | ForEach-Object { $_.FullName }

if ($files.Count -eq 0) {
	Write-Error "No files found to package in $functionDir"
	Pop-Location
	exit 1
}

Compress-Archive -LiteralPath $files -DestinationPath $outZip -Force
Pop-Location
Write-Host "Packaged $functionDir to $outZip"
