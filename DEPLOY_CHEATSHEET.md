# StealthRole — Deployment Cheat Sheet

Quick reference for deploying changes to production. No back-and-forth needed — just follow the steps.

---

## Architecture Overview

- **Frontend** (stealthrole.com): Next.js on **Vercel** — auto-deploys on `git push origin main`
- **Backend API** (api.stealthrole.com): FastAPI on **AWS ECS Fargate**
- **Chrome Extension**: Manual reload in `chrome://extensions`

---

## 1. FRONTEND (Vercel — automatic)

The frontend auto-deploys when you push to `main`. That's it.

```bash
cd ~/careeros
git add -A
git commit -m "your message"
git push origin main
# Vercel picks it up automatically — check https://vercel.com/dashboard
```

**Vercel Project IDs** (for reference):
- Frontend project: `prj_9xnMoZwVHVb2XC5fk1W8qqDuMEXU`
- Org: `team_Lqno6gMOEqFFuMsxD6I0Vvbj`

**Manual deploy** (if auto-deploy doesn't trigger):
```bash
cd ~/careeros/frontend
npx vercel --prod
```

**Env var**: `NEXT_PUBLIC_API_URL=https://api.stealthrole.com` (set in Vercel dashboard)

---

## 2. BACKEND API (AWS ECS)

### AWS Credentials
- **Profile**: `stealthrole`
- **Region**: `eu-west-1`
- **ECR Registry**: `459600194298.dkr.ecr.eu-west-1.amazonaws.com/stealthrole-api`
- **ECS Cluster**: `stealthrole`

### Deploy Steps

```bash
# Step 1: Build Docker image
cd ~/careeros
docker build -f docker/Dockerfile -t stealthrole-api .

# Step 2: Tag for ECR
docker tag stealthrole-api:latest 459600194298.dkr.ecr.eu-west-1.amazonaws.com/stealthrole-api:latest

# Step 3: Login to ECR
aws ecr get-login-password --region eu-west-1 --profile stealthrole | \
  docker login --username AWS --password-stdin 459600194298.dkr.ecr.eu-west-1.amazonaws.com

# Step 4: Push to ECR
docker push 459600194298.dkr.ecr.eu-west-1.amazonaws.com/stealthrole-api:latest

# Step 5: Force new deployment on ECS
aws ecs update-service \
  --cluster stealthrole \
  --service api \
  --force-new-deployment \
  --profile stealthrole \
  --region eu-west-1
```

### ECS Services

| Service | Purpose |
|---------|---------|
| `api` | FastAPI backend |
| `worker-default` | Background tasks |
| `worker-llm` | LLM processing |
| `beat` | Celery scheduler |

### Check Deployment Status

```bash
# Check deployment progress
aws ecs describe-services \
  --cluster stealthrole \
  --services api \
  --profile stealthrole \
  --region eu-west-1 \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount,rolloutState]' \
  --output table
```

---

## 3. CHROME EXTENSION

No deployment needed — just reload locally.

1. Open `chrome://extensions`
2. Find "StealthRole"
3. Click the refresh/reload button
4. Reload any open LinkedIn tabs

Extension files are in `~/careeros/extension/src/`:
- `linkedin-core.js` — content script (LinkedIn actions)
- `background.js` — service worker (message routing)
- `token-sync.js` — web app ↔ extension bridge
- `linkedin-messages.js` — message sync logic

---

## 4. FULL DEPLOY (everything at once)

```bash
cd ~/careeros
git add -A && git commit -m "deploy: your message" && git push origin main

# Frontend: done (Vercel auto-deploys)

# Backend:
docker build -f docker/Dockerfile -t stealthrole-api . && \
docker tag stealthrole-api:latest 459600194298.dkr.ecr.eu-west-1.amazonaws.com/stealthrole-api:latest && \
aws ecr get-login-password --region eu-west-1 --profile stealthrole | \
  docker login --username AWS --password-stdin 459600194298.dkr.ecr.eu-west-1.amazonaws.com && \
docker push 459600194298.dkr.ecr.eu-west-1.amazonaws.com/stealthrole-api:latest && \
aws ecs update-service --cluster stealthrole --service api --force-new-deployment --profile stealthrole --region eu-west-1

# Extension: reload in chrome://extensions
```

---

## 5. VERIFY

```bash
# Frontend
curl -s -o /dev/null -w "%{http_code}" https://stealthrole.com

# Backend API
curl https://api.stealthrole.com/health
```

---

## Quick Reference

| What | Where | How to deploy |
|------|-------|---------------|
| Frontend | Vercel | `git push origin main` |
| API | AWS ECS (eu-west-1) | Build → push ECR → force deploy |
| Extension | Local Chrome | Reload in chrome://extensions |
| Git repo | github.com/matteomantovani1982-stack/stealthrole | `main` branch |

---

## NOTE

All ECS service names are filled in. The API service is `api`.
