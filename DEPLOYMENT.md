# MyVault — Apne VPS par Deployment Guide (v.9x.design)

## OS
**Ubuntu 24.04 LTS** (ya 22.04 LTS) install karo — fresh minimal server.

## Step 1: DNS
Apne domain panel me `v.9x.design` ka **A record** VPS ki IP par point karo.

## Step 2: Emergent se "Save to GitHub"
Emergent me Save to GitHub button dabao → repo ban jayega (e.g. `github.com/USERNAME/REPO`).

## Step 3: VPS par one-time setup (root se SSH karke)
```bash
apt update && apt install -y git
git clone https://github.com/USERNAME/REPO.git /opt/myvault
bash /opt/myvault/scripts/setup-vps.sh https://github.com/USERNAME/REPO.git v.9x.design
```
Script sab install karta hai: nginx, Node 20 + yarn, Python venv, MongoDB 8, SSL (certbot), systemd service.
Private repo hai toh clone me token use karo: `https://TOKEN@github.com/USERNAME/REPO.git`

## Step 4: Auto-deploy (Save to GitHub → server auto-update)
VPS par SSH key banao:
```bash
ssh-keygen -t ed25519 -f /root/.ssh/github_deploy -N ""
cat /root/.ssh/github_deploy.pub >> /root/.ssh/authorized_keys
cat /root/.ssh/github_deploy   # ye PRIVATE key copy karo
```
GitHub repo → Settings → Secrets and variables → Actions → New repository secret (3 banao):
| Secret | Value |
|---|---|
| `VPS_HOST` | VPS ki IP |
| `VPS_USER` | `root` |
| `VPS_SSH_KEY` | upar wali private key (poori, BEGIN/END sahit) |

Bas! Ab jab bhi Emergent se **Save to GitHub** karoge, GitHub Action `scripts/deploy.sh` chala kar server update kar dega.

## Important
- `/etc/myvault.env` ka **backup** rakho — usme `ENCRYPTION_KEY` hai. Wo kho gayi toh saved passwords decrypt nahi honge.
- Backend logs: `journalctl -u myvault-backend -f`
- Manual update: `bash /opt/myvault/scripts/deploy.sh`
