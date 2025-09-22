# Portefeuille PEA + Crypto

Application mono-utilisateur pour suivre un portefeuille PEA et crypto (Binance) reposant sur :

- **Backend** : FastAPI + SQLAlchemy + APScheduler (base SQLite par défaut)
- **Frontend** : Next.js 14 + Tailwind CSS

## Fonctionnalités principales

- Calcul FIFO des positions et du P&L agrégé
- Imports CSV/ZIP, export complet des données et seed de démonstration optionnel
- Journal de trades et snapshots quotidiens (planification automatique et exécution manuelle)
- Configuration chiffrée de l'API Binance et alias de devises

## Architecture et arborescence

```text
backend/    → API FastAPI, tâches planifiées et services de calcul
frontend/   → UI Next.js/Tailwind
docs/       → Documentation (déploiement, format d'export)
samples/    → Exemples d'imports/export
sql/        → Scripts SQL et migrations Alembic
```

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

Depuis un terminal PowerShell :

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
./init_local.ps1
```

Le script réplique les étapes Linux : création de l'environnement virtuel, installation des dépendances puis lancement des serveurs backend et frontend (`NEXT_PUBLIC_API_BASE` pointant vers `http://localhost:8000`).

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

## Configuration applicative

Les variables d'environnement les plus utiles (toutes disponibles dans `.env.example`) :

| Clé | Description |
| --- | --- |
| `DATABASE_URL` | URL SQLAlchemy (SQLite par défaut). Les chemins relatifs sont automatiquement transformés en chemins absolus. |
| `TZ` | Fuseau horaire utilisé pour l'application et le scheduler. |
| `APP_SECRET` | Clé utilisée pour chiffrer des secrets comme l'API Binance. |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Identifiants API Binance en lecture seule. |
| `DEMO_SEED` | Active le seed de démonstration qui insère un exemple de transaction lors du premier démarrage. |

Une fois l'application lancée, l'UI permet également de sauvegarder les paramètres via l'API `/config` (clé Binance, alias de devises, etc.).

## Import / Export de données

- **Import** : `POST /transactions/import` accepte un fichier CSV ou ZIP (voir `samples/`). Le fichier doit au minimum contenir `transactions.csv` avec les colonnes décrites dans [docs/README_EXPORT.md](docs/README_EXPORT.md). Les références externes (`external_ref`) sont utilisées pour dédupliquer les lignes.
- **Export** : `GET /export/zip` retourne une archive ZIP contenant `transactions.csv`, `holdings.csv`, `snapshots.csv` et `journal_trades.csv`. Le détail des colonnes est documenté dans [docs/README_EXPORT.md](docs/README_EXPORT.md).

Après chaque import ou modification de transaction, les positions sont recalculées et mises en cache. Le cache est également invalidé lorsqu'on déclenche un snapshot manuel via `POST /snapshots/run`.

## Aperçu de l'API

| Endpoint | Description |
| --- | --- |
| `GET /` | Vérifie que l'application répond et renvoie le nom de l'app. |
| `GET /health` | Endpoint de santé minimal. |
| `GET /transactions` | Liste paginée (500 max) filtrable par source, type de portefeuille, actif ou opération. |
| `PATCH /transactions/{id}` / `DELETE /transactions/{id}` | Mise à jour ou suppression d'une transaction. |
| `GET /portfolio/holdings` | Retourne les positions agrégées et un résumé global. |
| `GET /portfolio/holdings/{identifier}` | Détail d'une position (historique FIFO, P&L réalisé, dividendes). |
| `GET /portfolio/pnl` | Historique du P&L global basé sur les snapshots. |
| `GET /snapshots` | Liste les snapshots, avec filtres temporels facultatifs. |
| `POST /snapshots/run` | Exécute immédiatement le calcul d'un snapshot. |
| `GET /journal` / `POST /journal` | Lecture et création de trades dans le journal. |
| `PATCH /journal/{id}` | Mise à jour d'un trade existant. |
| `GET /config/settings` / `POST /config/settings` | Lecture/écriture des paramètres applicatifs (alias de devises, préférences). |
| `POST /config/api/binance` | Sauvegarde chiffrée de la clé et du secret Binance. |
| `POST /config/wipe` | Purge complète des données (transactions, holdings, snapshots, journal…). |

Les endpoints retournent des schémas Pydantic décrits dans `backend/app/schemas/*`.

## Planification et tâches en arrière-plan

Au démarrage, l'application :

- applique les migrations Alembic et exécute un seed de démo si activé ;
- planifie le job `daily_snapshot` avec APScheduler en fonction des variables `SNAPSHOT_HOUR`/`SNAPSHOT_MINUTE` (par défaut 18:00) ;
- expose la tâche `run_snapshot` permettant de lancer manuellement un snapshot.

## Tests

- Backend :

  ```bash
  cd backend
  pytest
  ```

- Frontend :

  ```bash
  cd frontend
  npm run lint
  ```

## Déploiement

Pour une installation serveur sans Docker, un guide systemd + Nginx est disponible dans [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
