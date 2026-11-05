# WorkflowUI - (Re)start backend and frontend (developer mode)
# Run from WorkflowUI root: .\start-dev.ps1

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot
if (-not $RootDir) { $RootDir = Get-Location }

$BackendPort = 8000
$FrontendPort = 5173
$corsOrigins = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"

$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $UvicornCmd = "& '$VenvPython' -m uvicorn"
} else {
    Write-Warning "No .venv found. Falling back to uvicorn on PATH. Run .\install.ps1 for a local virtualenv."
    $UvicornCmd = "uvicorn"
}

function Stop-ProcessOnPort {
    param ([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($conn) {
        $conn | ForEach-Object {
            $processId = $_.OwningProcess
            if ($processId) {
                Write-Host "Stopping process on port $Port (PID $processId) ..."
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host "WorkflowUI (dev): stopping any existing backend (port $BackendPort) and frontend (port $FrontendPort) ..."
Stop-ProcessOnPort -Port $BackendPort
Stop-ProcessOnPort -Port $FrontendPort
Start-Sleep -Seconds 1

Write-Host "Starting backend (FastAPI) on port $BackendPort with APP_ENV=development ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\backend'; `$env:APP_ENV='development'; `$env:WORKFLOWUI_CORS_ORIGINS='$corsOrigins'; $UvicornCmd main:app --reload --port $BackendPort"

Start-Sleep -Seconds 2

Write-Host "Clearing frontend Vite cache (node_modules/.vite) to avoid stale Windows file locks ..."
$ViteCacheDir = Join-Path $RootDir "frontend\node_modules\.vite"
if (Test-Path $ViteCacheDir) {
    try {
        Remove-Item -LiteralPath $ViteCacheDir -Recurse -Force -ErrorAction Stop
    }
    catch {
        Write-Warning "Could not fully clear Vite cache at $ViteCacheDir. Dev server may still fail if another process is locking files."
    }
}

Write-Host "Starting frontend (SvelteKit) on port $FrontendPort ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\frontend'; `$env:BACKEND_URL='http://localhost:$BackendPort'; `$env:FRONTEND_PORT='$FrontendPort'; npm run dev -- --port $FrontendPort"

Write-Host ""
Write-Host "Backend (dev):  http://localhost:$BackendPort"
Write-Host "Frontend:       http://localhost:$FrontendPort"
Write-Host "Close the two new windows to stop the servers."
