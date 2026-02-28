@echo off
REM Build WorkflowUI Docker image using the version from frontend/package.json.
REM Usage: run from app root or anywhere; script lives in app root (one level up from docker/).
REM Set DOCKER_IMAGE_NAME to match Docker Hub (e.g. myorg/workflowui); default: workflowui

setlocal
cd /d "%~dp0"

if not defined DOCKER_IMAGE_NAME set DOCKER_IMAGE_NAME=workflowui

for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "(Get-Content -Raw 'frontend\package.json' | ConvertFrom-Json).version"`) do set VERSION=%%V
set TAG=%DOCKER_IMAGE_NAME%:%VERSION%

echo Building Docker image: %TAG%
docker build -f docker/Dockerfile -t %TAG% .
if errorlevel 1 exit /b 1
echo Built %TAG%
endlocal
