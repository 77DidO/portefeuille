#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $rootDir '.venv'
$pythonExe = if ($env:PYTHON) { $env:PYTHON } else { 'python' }

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment in $venvDir"
    & $pythonExe -m venv $venvDir
}

$venvScripts = Join-Path $venvDir 'Scripts'
$pythonCmd = Join-Path $venvScripts 'python.exe'

& $pythonCmd -m pip install --upgrade pip
& $pythonCmd -m pip install -r (Join-Path $rootDir 'backend/requirements.txt')

Push-Location (Join-Path $rootDir 'frontend')
try {
    npm install
}
finally {
    Pop-Location
}

if (-not $env:NEXT_PUBLIC_API_BASE) {
    $env:NEXT_PUBLIC_API_BASE = 'http://localhost:8000'
}

Write-Host 'Starting backend (uvicorn) and frontend (Next.js). Press Ctrl+C to stop both services.'

$backendProcess = Start-Process -FilePath $pythonCmd -ArgumentList '-m','uvicorn','app.main:app','--reload','--host','0.0.0.0','--port','8000' -WorkingDirectory (Join-Path $rootDir 'backend') -PassThru -NoNewWindow
$isWindows = try {
    [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
} catch {
    $false
}
$frontendFilePath = if ($isWindows) { 'cmd.exe' } else { 'npm' }
$frontendArguments = if ($isWindows) { @('/c','npm','run','dev') } else { @('run','dev') }
$frontendProcess = Start-Process -FilePath $frontendFilePath -ArgumentList $frontendArguments -WorkingDirectory (Join-Path $rootDir 'frontend') -PassThru -NoNewWindow

$cleanup = {
    param($backend, $frontend)
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontend -and -not $frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
    }
}

try {
    Wait-Process -Id $backendProcess.Id, $frontendProcess.Id
}
finally {
    & $cleanup.Invoke($backendProcess, $frontendProcess)
}
