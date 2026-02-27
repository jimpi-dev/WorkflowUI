# WorkflowUI — One-time setup: install backend and frontend dependencies
# Run from WorkflowUI root: .\install.ps1

$ErrorActionPreference = "Stop"
$RootDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }

Write-Host "WorkflowUI: installing dependencies..."
Write-Host ""

Write-Host "Backend (Python): pip install -r backend\requirements.txt"
Set-Location $RootDir\backend
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend install failed. Ensure Python 3.x and pip are installed."
    exit 1
}
Set-Location $RootDir

Write-Host ""
Write-Host "Frontend (Node): npm install in frontend/"
Set-Location $RootDir\frontend
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend install failed. Ensure Node.js and npm are installed."
    exit 1
}
Set-Location $RootDir

Write-Host ""
Write-Host "Done. Start the app with: .\start.ps1"
Write-Host "Optional: copy .env.example to .env and set COMFYUI_URL if needed."
