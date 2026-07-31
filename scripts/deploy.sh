#!/bin/bash
# Update script — pulls latest code from GitHub, rebuilds, restarts (run on VPS)
set -e

DOMAIN="${DOMAIN:-v.9x.design}"
cd /opt/myvault

echo "==> Pulling latest code..."
git fetch origin
git reset --hard origin/$(git rev-parse --abbrev-ref HEAD)

echo "==> Backend deps..."
sed -i '/emergentintegrations/d;/customer-assets.emergentagent.com/d' backend/requirements.txt
/opt/myvault/venv/bin/pip install -r backend/requirements.txt -q

echo "==> Building frontend..."
cd frontend
echo "REACT_APP_BACKEND_URL=https://$DOMAIN" > .env.production.local
yarn install
yarn build
rm -rf /var/www/myvault/*
cp -r build/* /var/www/myvault/

echo "==> Restarting backend..."
systemctl restart myvault-backend

echo "==> Deployed successfully at $(date)"
