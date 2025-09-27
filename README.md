# Portefeuille PEA + Crypto

Application mono-utilisateur permettant de suivre un portefeuille PEA et un portefeuille crypto via Binance. Elle s'articule autour d'une API FastAPI et d'une interface Next.js moderne capable de calculer automatiquement les positions et le P&L.

## Sommaire

1. [Vue d'ensemble](#vue-densemble)
2. [Fonctionnalités](#fonctionnalités)
3. [Architecture & arborescence](#architecture--arborescence)
4. [Mise en route](#mise-en-route)
5. [Configuration](#configuration)
6. [Import / Export de données](#import--export-de-données)
7. [API & tâches planifiées](#api--tâches-planifiées)
8. [Tests & qualité](#tests--qualité)
9. [Déploiement](#déploiement)
10. [Ressources complémentaires](#ressources-complémentaires)

## Vue d'ensemble

- **Backend** : FastAPI + SQLAlchemy + APScheduler (base SQLite par défaut)
- **Frontend** : Next.js 14 + Tailwind CSS
- **Base de données** : SQLite pour le développement, compatible avec PostgreSQL/MySQL via SQLAlchemy
- **Import/Export** : format CSV/ZIP documenté, CSV d'exemple fournis

L'application est pensée pour un déploiement mono-utilisateur : aucune gestion multi-compte n'est nécessaire, ce qui simplifie la configuration et la maintenance.

## Fonctionnalités

- **Suivi des positions** : calcul FIFO des positions, du P&L latent et réalisé, et des dividendes associés
- **Journal de trades** : suivi détaillé des entrées/sorties avec R multiples, statuts et notes personnalisées
- **Planification automatique** : snapshot quotidien planifié via APScheduler et déclenchable à la demande
- **Connecteurs d'import** : prise en charge des CSV personnalisés et des exports Binance (via `samples/`)
- **Sécurité** : stockage chiffré des identifiants API Binance grâce à une clé applicative
- **Expérience développeur** : scripts de démarrage rapide, migrations Alembic versionnées et formatage/linting automatique

## Architecture & arborescence

```text
backend/    → API FastAPI, tâches planifiées, services métier et scripts d'import
frontend/   → UI Next.js/Tailwind, composants React et pages App Router
docs/       → Documentation utilisateur et guides d'exploitation
samples/    → Exemples d'imports/export pour tests manuels et automatisés
sql/        → Scripts SQL et migrations Alembic
scripts/    → Utilitaires (seed de démo, tâches d'administration)
```

Les deux services communiquent via HTTP. Le frontend détecte automatiquement l'URL du backend lorsqu'ils sont servis sur la même machine (incluant les tunnels `https://…-3000…`).

## Mise en route

### Prérequis

- Python **3.11+** avec `venv` et `pip`
- Node.js **18+** et `npm`
- SQLite (installé par défaut sur la majorité des distributions)

### Installation automatisée (Linux / macOS / WSL)

```bash
./init_local.sh
```

Le script :

1. crée `.venv` puis installe les dépendances backend ;
2. exécute `npm install` dans `frontend/` ;
3. démarre simultanément `uvicorn app.main:app` et `npm run dev` ;
4. ajuste automatiquement l'URL API côté frontend (détection locale ou tunnels).

Arrêter les services avec `Ctrl+C` ferme proprement les deux processus.

### Installation automatisée (Windows PowerShell)

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
./init_local.ps1
```

Les étapes sont identiques au script Bash et prennent en charge la détection automatique du backend.

### Installation manuelle

1. Copier la configuration d'exemple :

   ```bash
   cp .env.example .env
   ```

2. Créer l'environnement Python :

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. Démarrer le backend FastAPI :

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Installer et lancer le frontend Next.js :

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

Le frontend écoute par défaut sur http://localhost:3000 et contacte automatiquement le backend sur http://localhost:8000.

### Docker Compose

Un fichier `docker-compose.yml` est fourni pour exécuter les deux services dans des conteneurs distincts.

```bash
docker compose up --build
```

Par défaut, le frontend détecte l'API exposée sur `http://backend:8000`. Décommentez `NEXT_PUBLIC_API_BASE` dans `docker-compose.yml` si vous souhaitez forcer un autre endpoint (ex. reverse proxy externe).

### Migrations Alembic

```bash
alembic upgrade head
```

Depuis `backend/` :

```bash
cd backend
alembic -c ../alembic.ini upgrade head
```

Les migrations sont appliquées automatiquement au démarrage grâce au module `app.db.init`, mais l'exécution manuelle reste utile pour les environnements CI/CD.

## Configuration

Les variables essentielles (voir `.env.example`) :

| Clé | Description |
| --- | --- |
| `DATABASE_URL` | URL SQLAlchemy. Les chemins relatifs sont convertis en absolu (utile pour SQLite). |
| `TZ` | Fuseau horaire utilisé pour la planification APScheduler et les dates affichées. |
| `APP_SECRET` | Clé AES utilisée pour chiffrer les secrets (API Binance). |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Accès API Binance en lecture seule. |
| `DEMO_SEED` | `true` pour insérer un jeu de données de démonstration au premier démarrage. |
| `SNAPSHOT_HOUR` / `SNAPSHOT_MINUTE` | Heure du snapshot quotidien automatique. |

L'interface permet de gérer dynamiquement les alias de devises, le seed Binance et la purge complète via les endpoints `/config`.

## Import / Export de données

- **Import CSV/ZIP** via `POST /transactions/import`. L'API déduplique les lignes grâce à `transaction_uid` et retourne un rapport détaillant les lignes créées, mises à jour ou ignorées.
- **Export complet** via `GET /export/zip`. Le ZIP contient `transactions.csv`, `holdings.csv`, `snapshots.csv` et `journal_trades.csv` dont la structure est décrite dans [docs/README_EXPORT.md](docs/README_EXPORT.md).
- **Exemples** : le dossier [`samples/`](samples/) fournit des fichiers prêts à l'emploi pour l'import manuel ou les tests d'intégration.

Chaque import déclenche une invalidation du cache de positions suivie d'un recalcul immédiat.

## API & tâches planifiées

### Endpoints principaux

| Endpoint | Description |
| --- | --- |
| `GET /` | Vérifie l'état de l'application. |
| `GET /health` | Check de santé minimal pour vos probes. |
| `GET /transactions` | Liste paginée (500 max) filtrable par source, portefeuille, actif, type d'opération. |
| `PATCH /transactions/{id}` / `DELETE /transactions/{id}` | Mise à jour ou suppression d'une transaction. |
| `GET /portfolio/holdings` | Positions agrégées, P&L, PRU et exposition par devise. |
| `GET /portfolio/holdings/{identifier}` | Historique FIFO détaillé d'une position. |
| `GET /portfolio/pnl` | Historique des snapshots agrégés. |
| `GET /snapshots` / `POST /snapshots/run` | Gestion des snapshots planifiés et manuels. |
| `GET /journal` / `POST /journal` | Lecture/écriture dans le journal de trades. |
| `PATCH /journal/{id}` | Mise à jour d'un trade existant. |
| `GET /config/settings` / `POST /config/settings` | Lecture et écriture des paramètres (alias, préférences d'affichage). |
| `POST /config/api/binance` | Sauvegarde chiffrée de la clé/secret Binance. |
| `POST /config/wipe` | Purge complète (transactions, holdings, snapshots, journal). |

Les schémas Pydantic correspondants se trouvent dans `backend/app/schemas/`.

### Planification & tâches d'arrière-plan

Au démarrage :

1. les migrations Alembic sont appliquées ;
2. un seed de démonstration est exécuté si `DEMO_SEED=true` ;
3. le job `daily_snapshot` est programmé via APScheduler selon `SNAPSHOT_HOUR`/`SNAPSHOT_MINUTE` ;
4. le service expose un endpoint pour déclencher manuellement les snapshots (`POST /snapshots/run`).

Un job de recalcul est également déclenché après chaque import/export pour maintenir les agrégats à jour.

## Tests & qualité

### Tests backend

```bash
cd backend
pytest
```

### Qualité frontend

```bash
cd frontend
npm run lint
```

Des scripts additionnels (`npm run test`, `npm run typecheck`) peuvent être ajoutés selon vos besoins.

## Déploiement

Pour un déploiement serveur sans Docker, consultez le guide [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (systemd + Nginx, HTTPS, journalisation, mises à jour).

## Ressources complémentaires

- [docs/README_EXPORT.md](docs/README_EXPORT.md) : structure des CSV d'import/export
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) : guide d'installation serveur
- [samples/](samples/) : jeux de données d'exemple
- [scripts/](scripts/) : utilitaires (seed de démo, tâches ponctuelles)
