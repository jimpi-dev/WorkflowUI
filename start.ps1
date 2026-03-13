# WorkflowUI — (Re)start backend and frontend
# Run from WorkflowUI root: .\start.ps1

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot
if (-not $RootDir) { $RootDir = Get-Location }

$BackendPort = 8000
$FrontendPort = 5173

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

Write-Host "WorkflowUI: stopping any existing backend (port $BackendPort) and frontend (port $FrontendPort) ..."
Stop-ProcessOnPort -Port $BackendPort
Stop-ProcessOnPort -Port $FrontendPort
Start-Sleep -Seconds 1

Write-Host "Starting backend (FastAPI) on port $BackendPort with APP_ENV=production ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\backend'; `$env:APP_ENV='production'; uvicorn main:app --reload --port $BackendPort"

Start-Sleep -Seconds 2

Write-Host "Starting frontend (SvelteKit) on port $FrontendPort ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\frontend'; npm run dev"

Write-Host ""
Write-Host "Backend:  http://localhost:$BackendPort"
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Close the two new windows to stop the servers."
