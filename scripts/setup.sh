#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

usage() {
  cat <<'USAGE'
Script utilitaire pour installer et lancer Portefeuille.

Usage :
  scripts/setup.sh <commande>

Commandes disponibles :
  install   Installe les dépendances backend et frontend et prépare les fichiers d'environnement.
  backend   Lance le backend FastAPI en mode développement.
  frontend  Lance le frontend Next.js en mode développement.
  docker    Construit et lance l'application via docker-compose.
  test      Exécute la suite de tests backend.
  help      Affiche ce message d'aide.
USAGE
}

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "Création de l'environnement virtuel Python dans $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
}

cmd_install() {
  if [ -f "$ROOT_DIR/.env.example" ]; then
    if [ ! -f "$ROOT_DIR/.env" ]; then
      echo "Copie de .env.example vers .env"
      cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    else
      echo ".env existe déjà, aucune copie nécessaire"
    fi
  fi

  ensure_venv
  echo "Mise à jour de pip"
  pip install --upgrade pip
  echo "Installation des dépendances backend"
  pip install -r "$BACKEND_DIR/requirements.txt"

  if command -v npm >/dev/null 2>&1; then
    echo "Installation des dépendances frontend"
    (cd "$FRONTEND_DIR" && npm install)
  else
    echo "npm est introuvable, installation du frontend ignorée" >&2
  fi

  echo "Installation terminée"
}

cmd_backend() {
  ensure_venv
  exec uvicorn app.main:app --reload --app-dir "$BACKEND_DIR"
}

cmd_frontend() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm est requis pour lancer le frontend." >&2
    exit 1
  fi
  exec npm run dev --prefix "$FRONTEND_DIR"
}

cmd_docker() {
  exec docker-compose up --build
}

cmd_test() {
  ensure_venv
  (cd "$BACKEND_DIR" && pytest)
}

main() {
  local cmd="${1:-help}"
  case "$cmd" in
    install) cmd_install ;;
    backend) cmd_backend ;;
    frontend) cmd_frontend ;;
    docker) cmd_docker ;;
    test) cmd_test ;;
    help|--help|-h) usage ;;
    *)
      echo "Commande inconnue : $cmd" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
