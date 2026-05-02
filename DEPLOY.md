# GitHub Actions Deployment Setup

## Required Secrets

To use the auto-deploy workflow, you need to add these secrets to your GitHub repository:

### SSH Deployment (Primary Method)
1. **DEPLOY_PRIVATE_KEY** - Your SSH private key for the server
2. **DEPLOY_HOST** - Server IP/hostname (e.g., `192.168.1.29`)
3. **DEPLOY_USER** - SSH username (e.g., `node`)
4. **DEPLOY_PATH** - Deploy directory (e.g., `/home/node/.openclaw/workspace/reminders-bridge`)

### Portainer API (Fallback)
5. **PORTAINER_URL** - Portainer API URL (e.g., `https://192.168.1.29:9443`)
6. **PORTAINER_KEY** - Your Portainer API key

---

## How to Add Secrets to GitHub

### Via GitHub Web UI:
1. Go to: https://github.com/mikemarre-creator/reminders-bridge/settings/secrets/actions
2. Click "New repository secret"
3. Add each secret listed above

### Via GitHub CLI (if you have it):
```bash
gh secret set DEPLOY_HOST -b "192.168.1.29"
gh secret set DEPLOY_USER -b "node"
gh secret set DEPLOY_PATH -b "/home/node/.openclaw/workspace/reminders-bridge"
gh secret set PORTAINER_URL -b "https://192.168.1.29:9443"
gh secret set PORTAINER_KEY -b "ptr_3Zxj5n5CWvRJpz7fPpaukPisj5qjYL1ZRyUz8U0g5g8="
```

---

## SSH Key Setup

### Generate a Deploy Key (if you don't have one):
On your server:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -C "github-actions"
cat ~/.ssh/github_deploy  # Add this as DEPLOY_PRIVATE_KEY
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
```

---

## Deployment Flow

When you push to `main`:

1. ✅ Tests and linting run
2. ✅ Docker build succeeds
3. ✅ SSH into server and:
   - Pull latest code
   - Rebuild Docker image
   - Restart container
4. ⚠️ If SSH fails, fallback to Portainer API
5. 📋 Health check runs

---

## Monitor Deployments

View workflow runs at:
```
https://github.com/mikemarre-creator/reminders-bridge/actions
```

Each push will trigger the deployment automatically! 🚀

---

## Manual Deployment

You can also manually trigger deployment by:
1. Going to Actions tab
2. Click "Auto Deploy to Server"
3. Click "Run workflow" → "Run workflow"

---

## Troubleshooting

- **SSH Connection Failed**: Check DEPLOY_HOST, DEPLOY_USER, and DEPLOY_PRIVATE_KEY
- **Permission Denied**: Ensure deploy key is in `~/.ssh/authorized_keys` on server
- **Container Not Found**: Check container name matches `openclaw-reminders-bridge`
- **Health Check Fails**: Container might be starting up, this is normal

