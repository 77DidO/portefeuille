[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'backend', 'frontend', 'docker', 'test', 'help')]
    [string]$Command = 'help'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
    @'
Script utilitaire PowerShell pour installer et lancer Portefeuille.

Utilisation :
  ./scripts/setup.ps1 <commande>

Commandes disponibles :
  install   Installe les dépendances backend et frontend et prépare les fichiers d'environnement.
  backend   Lance le backend FastAPI en mode développement.
  frontend  Lance le frontend Next.js en mode développement.
  docker    Construit et lance l'application via docker-compose.
  test      Exécute la suite de tests backend.
  help      Affiche ce message d'aide.
'@
}

function Resolve-RepoPath {
    param(
        [string]$RelativePath = ''
    )

    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $rootPath = Convert-Path (Join-Path $scriptDir '..')

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        return $rootPath
    }
    return Convert-Path (Join-Path $rootPath $RelativePath)
}

$RootDir = Resolve-RepoPath
$VenvDir = Join-Path $RootDir '.venv'
$BackendDir = Resolve-RepoPath 'backend'
$FrontendDir = Resolve-RepoPath 'frontend'

function Ensure-Venv {
    if (-not (Test-Path -Path $VenvDir)) {
        Write-Host "Création de l'environnement virtuel Python dans $VenvDir"
        python -m venv $VenvDir | Out-Null
    }
    $pythonPath = Join-Path $VenvDir 'Scripts/python.exe'
    if (-not (Test-Path -Path $pythonPath)) {
        throw "Python introuvable dans l'environnement virtuel : $pythonPath"
    }
    return $pythonPath
}

function Invoke-Python {
    param(
        [Parameter(Mandatory)]
        [string]$Module,
        [Parameter()]
        [string[]]$Arguments = @()
    )

    $python = Ensure-Venv
    & $python -m $Module @Arguments
}

switch ($Command) {
    'install' {
        $envExample = Join-Path $RootDir '.env.example'
        $envFile = Join-Path $RootDir '.env'
        if (Test-Path -Path $envExample -PathType Leaf) {
            if (-not (Test-Path -Path $envFile -PathType Leaf)) {
                Write-Host "Copie de .env.example vers .env"
                Copy-Item -Path $envExample -Destination $envFile
            } else {
                Write-Host ".env existe déjà, aucune copie nécessaire"
            }
        }

        Write-Host "Mise à jour de pip"
        Invoke-Python -Module 'pip' -Arguments @('install', '--upgrade', 'pip')

        Write-Host "Installation des dépendances backend"
        $requirements = Join-Path $BackendDir 'requirements.txt'
        Invoke-Python -Module 'pip' -Arguments @('install', '-r', $requirements)

        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Write-Host "Installation des dépendances frontend"
            Push-Location $FrontendDir
            try {
                npm install
            } finally {
                Pop-Location
            }
        } else {
            Write-Warning "npm est introuvable, installation du frontend ignorée"
        }

        Write-Host "Installation terminée"
    }
    'backend' {
        $uvicornArgs = @('uvicorn', 'app.main:app', '--reload', '--app-dir', $BackendDir)
        Invoke-Python -Module $uvicornArgs[0] -Arguments $uvicornArgs[1..($uvicornArgs.Length - 1)]
    }
    'frontend' {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
            throw "npm est requis pour lancer le frontend."
        }
        Push-Location $FrontendDir
        try {
            npm run dev
        } finally {
            Pop-Location
        }
    }
    'docker' {
        docker-compose up --build
    }
    'test' {
        Push-Location $BackendDir
        try {
            Invoke-Python -Module 'pytest'
        } finally {
            Pop-Location
        }
    }
    Default {
        Show-Usage
    }
}
