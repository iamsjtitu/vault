#!/bin/bash
# One-time VPS setup for MyVault (Ubuntu 22.04/24.04)
# Usage: bash setup-vps.sh https://github.com/YOUR_USER/YOUR_REPO.git v.9x.design
set -e

REPO_URL="$1"
DOMAIN="${2:-v.9x.design}"

if [ -z "$REPO_URL" ]; then
  echo "Usage: bash setup-vps.sh <github-repo-url> [domain]"
  exit 1
fi

echo "==> Installing system packages..."
apt update
apt install -y nginx git curl python3-venv python3-pip gnupg certbot python3-certbot-nginx

echo "==> Installing Node.js 20 + yarn..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g yarn

echo "==> Installing MongoDB 8.0..."
if ! command -v mongod >/dev/null; then
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
  echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/8.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-8.0.list
  apt update && apt install -y mongodb-org
fi
systemctl enable --now mongod

echo "==> Cloning repo to /opt/myvault..."
if [ ! -d /opt/myvault ]; then
  git clone "$REPO_URL" /opt/myvault
fi

echo "==> Python venv + backend deps..."
python3 -m venv /opt/myvault/venv
/opt/myvault/venv/bin/pip install -r /opt/myvault/backend/requirements.txt -q

echo "==> Generating secrets in /etc/myvault.env (created once, never overwritten)..."
if [ ! -f /etc/myvault.env ]; then
  JWT_SECRET=$(/opt/myvault/venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
  ENC_KEY=$(/opt/myvault/venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  cat > /etc/myvault.env <<ENVEOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=myvault
CORS_ORIGINS=https://$DOMAIN
JWT_SECRET=$JWT_SECRET
ENCRYPTION_KEY=$ENC_KEY
ENVEOF
  chmod 600 /etc/myvault.env
  echo "!!! IMPORTANT: /etc/myvault.env ka backup le lo. ENCRYPTION_KEY kho gayi toh saved passwords decrypt nahi honge !!!"
fi

echo "==> Creating systemd service..."
cat > /etc/systemd/system/myvault-backend.service <<'UNITEOF'
[Unit]
Description=MyVault FastAPI backend
After=network.target mongod.service

[Service]
WorkingDirectory=/opt/myvault/backend
EnvironmentFile=/etc/myvault.env
ExecStart=/opt/myvault/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
UNITEOF
systemctl daemon-reload
systemctl enable --now myvault-backend

echo "==> Building frontend..."
mkdir -p /var/www/myvault
cd /opt/myvault/frontend
echo "REACT_APP_BACKEND_URL=https://$DOMAIN" > .env.production.local
yarn install
yarn build
rm -rf /var/www/myvault/*
cp -r build/* /var/www/myvault/

echo "==> Configuring nginx..."
cat > /etc/nginx/sites-available/myvault <<NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;
    root /var/www/myvault;
    index index.html;
    client_max_body_size 15M;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location /api {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri /index.html;
    }
}
NGINXEOF
ln -sf /etc/nginx/sites-available/myvault /etc/nginx/sites-enabled/myvault
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> SSL certificate (certbot)..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || echo "Certbot failed — pehle DNS me A record point karo, phir: certbot --nginx -d $DOMAIN"

echo ""
echo "======================================"
echo " DONE! App live at: https://$DOMAIN"
echo " Backend logs: journalctl -u myvault-backend -f"
echo " Update anytime: bash /opt/myvault/scripts/deploy.sh"
echo "======================================"
