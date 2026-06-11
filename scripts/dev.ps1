# Start the backend (FastAPI) + frontend (Vite). The backend opens in its own
# window; the frontend runs in this one. Uses the venv's Python directly.
#   Run from the repo root:  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
  Write-Host "No backend venv found. First-time setup:" -ForegroundColor Yellow
  Write-Host "  cd backend; python -m venv .venv"
  Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt"
  exit 1
}

Write-Host "Backend  -> http://127.0.0.1:8000"
Write-Host "Frontend -> http://localhost:5173"

Start-Process -FilePath $py `
  -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000' `
  -WorkingDirectory (Join-Path $root 'backend')

Set-Location (Join-Path $root 'frontend')
npm run dev
