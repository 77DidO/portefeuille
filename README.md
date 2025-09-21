# Portefeuille PEA + Crypto

Application mono-utilisateur pour suivre un portefeuille PEA et Crypto (Binance). Cette base fournit un backend FastAPI et un frontend Next.js/Tailwind avec Docker.

## Démarrage rapide

### Avec le script utilitaire

> Prérequis : `python3`, `npm` et (facultatif) `docker`/`docker-compose` doivent être disponibles sur votre machine.

```bash
# Installation des dépendances backend et frontend
./scripts/setup.sh install

# Lancement du backend FastAPI
./scripts/setup.sh backend

# Lancement du frontend Next.js
./scripts/setup.sh frontend
```

Autres commandes utiles :

```bash
# Exécuter les tests backend
./scripts/setup.sh test

# Démarrer l'application via Docker
./scripts/setup.sh docker
```

### Installation manuelle

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

Frontend :

```bash
cd frontend
npm install
npm run dev
```

Ou via Docker :

```bash
docker-compose up --build
```

## Tests

```bash
cd backend
pytest
```

## Fonctionnalités principales
- Authentification JWT mono-utilisateur
- Calcul FIFO des positions et P&L
- Import/export CSV & ZIP
- Snapshots quotidiens planifiés (APScheduler)
- UI Next.js avec dashboard et configuration
