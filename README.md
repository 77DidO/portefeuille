# Portefeuille PEA + Crypto

Application mono-utilisateur pour suivre un portefeuille PEA et Crypto (Binance). Cette base fournit un backend FastAPI (SQLite) et un frontend Next.js/Tailwind.

## Prérequis

- Python **3.11+** avec `venv` et `pip`
- Node.js **18+** et `npm`
- SQLite (installé par défaut sur la plupart des distributions)

## Installation locale

### Script automatisé (Linux / macOS / WSL)

Un script Bash est fourni pour installer les dépendances et lancer les deux services :

```bash
./init_local.sh
```

Le script crée un environnement virtuel Python local (`.venv`), installe les dépendances backend, exécute `npm install` dans `frontend/` puis lance :

- Backend : `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend : `NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev`

Appuyez sur `Ctrl+C` pour arrêter les deux services.

### Script automatisé (Windows PowerShell)

Sur Windows, un script PowerShell est fourni. Depuis un terminal PowerShell :

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
./init_local.ps1
```


Le script crée l'environnement virtuel Python (`.venv`), installe les dépendances, exécute `npm install` puis lance :

- Backend : `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend : `npm run dev` avec `NEXT_PUBLIC_API_BASE` défini par défaut sur `http://localhost:8000`

Utilisez `Ctrl+C` pour stopper les deux services.

### Installation manuelle

1. Copier la configuration d'exemple si besoin :

   ```bash
   cp .env.example .env
   ```

2. Préparer et activer l'environnement Python :

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. Lancer le backend FastAPI depuis le dossier `backend/` :

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Installer et lancer le frontend Next.js :

   ```bash
   cd frontend
   npm install
   NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
   ```

Le backend est accessible sur http://localhost:8000 et le frontend sur http://localhost:3000.

## Tests

```bash
cd backend
pytest
```

## Fonctionnalités principales
- Accès direct mono-utilisateur (aucune authentification)
- Calcul FIFO des positions et P&L
- Import/export CSV & ZIP
- Snapshots quotidiens planifiés (APScheduler)
- UI Next.js avec dashboard et configuration

## Déploiement

Pour une installation serveur sans Docker, un guide systemd + Nginx est disponible dans [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
