# Déploiement sans Docker (systemd + Nginx)

Ce guide décrit une installation de l'application sur un serveur Linux en utilisant `systemd` pour superviser le backend FastAPI et le frontend Next.js, ainsi que Nginx comme reverse-proxy.

## Prérequis serveur

- Distribution Linux avec `systemd` et `nginx`
- Python 3.11+
- Node.js 18+
- `git`, `pip`, `npm`
- Accès sudo

## Arborescence recommandée

```text
/opt/portefeuille/
├── backend/
├── frontend/
├── .venv/
└── .env
```

## Installation des sources et dépendances

1. Créer un utilisateur système dédié :

   ```bash
   sudo useradd --system --create-home --shell /usr/sbin/nologin portefeuille
   ```

2. Cloner le dépôt :

   ```bash
   sudo mkdir -p /opt/portefeuille
   sudo chown portefeuille:portefeuille /opt/portefeuille
   sudo -u portefeuille git clone https://example.com/portefeuille.git /opt/portefeuille
   ```

3. Créer l'environnement virtuel Python et installer les dépendances :

   ```bash
   sudo -u portefeuille python3.11 -m venv /opt/portefeuille/.venv
   sudo -u portefeuille /opt/portefeuille/.venv/bin/pip install --upgrade pip
   sudo -u portefeuille /opt/portefeuille/.venv/bin/pip install -r /opt/portefeuille/backend/requirements.txt
   ```

4. Installer les dépendances frontend et construire l'application :

   ```bash
   cd /opt/portefeuille/frontend
   sudo -u portefeuille npm install
   sudo -u portefeuille NEXT_PUBLIC_API_BASE="https://votre-domaine" npm run build
   ```

5. Copier et adapter le fichier d'environnement :

   ```bash
   sudo -u portefeuille cp /opt/portefeuille/.env.example /opt/portefeuille/.env
   sudo -u portefeuille nano /opt/portefeuille/.env
   ```

## Services systemd

Créer deux unités systemd : une pour le backend FastAPI (`uvicorn`) et une pour le frontend Next.js (`next start`).

### Backend (`/etc/systemd/system/portefeuille-backend.service`)

```ini
[Unit]
Description=Portefeuille FastAPI backend
After=network.target

[Service]
User=portefeuille
Group=portefeuille
WorkingDirectory=/opt/portefeuille/backend
Environment="ENV_FILE=/opt/portefeuille/.env"
Environment="PORT=8000"
ExecStart=/opt/portefeuille/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Frontend (`/etc/systemd/system/portefeuille-frontend.service`)

```ini
[Unit]
Description=Portefeuille Next.js frontend
After=network.target portefeuille-backend.service

[Service]
User=portefeuille
Group=portefeuille
WorkingDirectory=/opt/portefeuille/frontend
Environment="PORT=3000"
Environment="NEXT_PUBLIC_API_BASE=https://votre-domaine"
ExecStart=/usr/bin/npm run start -- --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> **Remarque :** `npm run start` démarre le serveur Next.js à partir du build généré par `npm run build`. Assurez-vous de relancer `npm run build` après chaque mise à jour.

Activer et démarrer les services :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now portefeuille-backend.service portefeuille-frontend.service
sudo systemctl status portefeuille-backend.service portefeuille-frontend.service
```

## Configuration Nginx

Créer un fichier de configuration (ex. `/etc/nginx/sites-available/portefeuille.conf`) :

```nginx
server {
    listen 80;
    server_name votre-domaine;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activer le site et recharger Nginx :

```bash
sudo ln -s /etc/nginx/sites-available/portefeuille.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Pour activer HTTPS, utilisez `certbot` ou tout autre outil compatible et adaptez la configuration pour écouter sur `443`.

## Mises à jour

1. Arrêter les services :

   ```bash
   sudo systemctl stop portefeuille-frontend.service portefeuille-backend.service
   ```

2. Mettre à jour le code :

   ```bash
   cd /opt/portefeuille
   sudo -u portefeuille git pull
   ```

3. Réinstaller les dépendances si nécessaire :

   ```bash
   sudo -u portefeuille /opt/portefeuille/.venv/bin/pip install -r backend/requirements.txt
   cd frontend
   sudo -u portefeuille npm install
   sudo -u portefeuille NEXT_PUBLIC_API_BASE="https://votre-domaine" npm run build
   ```

4. Redémarrer les services :

   ```bash
   sudo systemctl start portefeuille-backend.service portefeuille-frontend.service
   ```

## Journalisation

Consulter les journaux :

```bash
sudo journalctl -u portefeuille-backend.service -f
sudo journalctl -u portefeuille-frontend.service -f
```

Nginx journalise dans `/var/log/nginx/access.log` et `/var/log/nginx/error.log`.
