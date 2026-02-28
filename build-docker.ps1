# Build WorkflowUI Docker image using the version from frontend/package.json.
# Usage: run from app root or anywhere; script lives in app root (one level up from docker/).
# Set $env:DOCKER_IMAGE_NAME to match Docker Hub (e.g. myorg/workflowui); default: workflowui

$ErrorActionPreference = 'Stop'
$AppRoot = $PSScriptRoot
Set-Location $AppRoot

$pkg = Get-Content -Raw (Join-Path $AppRoot 'frontend\package.json') | ConvertFrom-Json
$Version = $pkg.version
$ImageName = if ($env:DOCKER_IMAGE_NAME) { $env:DOCKER_IMAGE_NAME } else { 'workflowui' }
$Tag = "${ImageName}:${Version}"

Write-Host "Building Docker image: $Tag (from $AppRoot)"
docker build -f docker/Dockerfile -t $Tag .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Built $Tag"
