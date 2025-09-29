#!/usr/bin/env pwsh
# Lancer backend FastAPI + frontend Next.js (Windows)
param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000,
  [string]$ApiBase = $env:NEXT_PUBLIC_API_BASE,   # mettre une URL si backend ≠ 8000
  [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $root '.venv'
$python  = if ($env:PYTHON) { $env:PYTHON } else { 'py' }

# --- venv & deps ---
if (-not (Test-Path $venvDir)) {
  Write-Host "Creating virtual environment in $venvDir"
  & $python -3.12 -m venv $venvDir
}
$pyExe = Join-Path $venvDir 'Scripts\python.exe'
& $pyExe -m pip install --upgrade pip | Out-Host
& $pyExe -m pip install -r (Join-Path $root 'backend\requirements.txt') | Out-Host

Push-Location (Join-Path $root 'frontend')
try { npm install | Out-Host } finally { Pop-Location }

# --- lance backend ---
Write-Host "Starting backend on http://127.0.0.1:$BackendPort ..."
$backend = Start-Process -FilePath $pyExe `
  -ArgumentList @('-m','uvicorn','app.main:app','--reload','--host','0.0.0.0','--port',"$BackendPort") `
  -WorkingDirectory (Join-Path $root 'backend') -PassThru -NoNewWindow

Start-Sleep -Seconds 2
$probe = Test-NetConnection 127.0.0.1 -Port $BackendPort
if (-not $probe.TcpTestSucceeded) {
  Write-Warning "Rien n’écoute sur 127.0.0.1:$BackendPort. Si un VPN (CyberGhost) est actif, désactive le Kill Switch et autorise le LAN/loopback."
}

# --- lance frontend ---
if ($ApiBase) {
  Write-Host "Frontend utilisera NEXT_PUBLIC_API_BASE=$ApiBase"
  $env:NEXT_PUBLIC_API_BASE = $ApiBase
} else {
  Remove-Item Env:NEXT_PUBLIC_API_BASE -ErrorAction SilentlyContinue
  Write-Host "Aucune NEXT_PUBLIC_API_BASE → auto-détection (8000 en local)."
}

Write-Host "Starting frontend (Next.js dev) on http://localhost:$FrontendPort ..."
$frontend = Start-Process -FilePath "cmd.exe" `
  -ArgumentList '/c','npm','run','dev' `
  -WorkingDirectory (Join-Path $root 'frontend') -PassThru -NoNewWindow

# --- ouvre le navigateur (optionnel) ---
if ($OpenBrowser) {
  $brave = "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
  $url = "http://localhost:$FrontendPort"
  if (Test-Path $brave) { Start-Process $brave $url } else { Start-Process cmd.exe "/c start $url" }
}

Write-Host "Backend PID  : $($backend.Id)"
Write-Host "Frontend PID : $($frontend.Id)"
Write-Host "`nCtrl+C dans cette fenêtre pour tout arrêter."

# --- arrêt propre ---
$cleanup = {
  param($b,$f)
  foreach ($p in @($b,$f)) {
    if ($p -and -not $p.HasExited) {
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
  }
}
try {
  Wait-Process -Id $backend.Id, $frontend.Id
} finally {
  & $cleanup.Invoke($backend, $frontend)
}
