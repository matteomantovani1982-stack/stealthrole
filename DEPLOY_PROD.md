# StealthRole — Production Deployment Guide

> Step-by-step deployment. Complete [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md) first.

---

## Architecture

```
                    ┌──────────┐
                    │  Nginx   │ ← SSL termination, static files
                    │ :80/:443 │
                    └────┬─────┘
                         │
              ┌──────────┴──────────┐
              │                     │
        ┌─────┴─────┐       ┌──────┴──────┐
        │  Next.js   │       │  FastAPI    │
        │  Frontend  │       │  API :8000  │
        │  (static)  │       └──────┬──────┘
        └────────────┘              │
                          ┌─────────┼─────────┐
                          │         │         │
                    ┌─────┴──┐ ┌────┴───┐ ┌───┴──────┐
                    │worker  │ │worker  │ │worker    │
                    │default │ │llm (2) │ │rendering │
                    └────────┘ └────────┘ └──────────┘
                          │         │         │
                    ┌─────┴─────────┴─────────┴─────┐
                    │         Redis + PostgreSQL      │
                    └────────────────────────────────┘
                                    │
                              ┌─────┴─────┐
                              │ Celery    │
                              │ Beat      │ ← daily_scout_scan
                              └───────────┘    periodic_email_sync
                                               periodic_calendar_sync
```

External services: Anthropic (Claude), Serper, Twilio (WhatsApp), Stripe, Google OAuth, S3

---

## Step 1: Provision Server

```bash
# Ubuntu 22.04, 4+ vCPU, 8+ GB RAM
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# Clone repo
git clone https://github.com/your-org/stealthrole.git /opt/stealthrole
cd /opt/stealthrole
```

---

## Step 2: Configure Environment

```bash
cp .env.production.example .env.production
```

Fill in ALL values. Reference: [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md)

### Required `.env.production`:

```env
# App
APP_ENV=production
APP_NAME=StealthRole
DEBUG=false
SECRET_KEY=<openssl rand -hex 32>

# Database
DATABASE_URL=postgresql+asyncpg://stealthrole:STRONG_PASSWORD@postgres:5432/stealthrole
POSTGRES_PASSWORD=STRONG_PASSWORD

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Claude (packs, conversation analysis, signal scoring)
ANTHROPIC_API_KEY=sk-ant-api03-...
CLAUDE_MODEL=claude-sonnet-4-6

# Serper (market signals, LinkedIn profile import)
SERPER_API_KEY=<your-key>

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=<your-token>
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886    # sandbox initially, replace with production number

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_STARTER_MONTHLY=price_...

# Google OAuth (Gmail integration)
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...

# Email token encryption (for stored OAuth tokens)
EMAIL_TOKEN_ENCRYPTION_KEY=<Fernet.generate_key()>

# S3 Storage
S3_ACCESS_KEY_ID=<your-key>
S3_SECRET_ACCESS_KEY=<your-secret>
S3_BUCKET_NAME=stealthrole-production
S3_REGION=me-south-1

# SMTP (transactional email)
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASSWORD=re_...
SMTP_FROM=noreply@stealthrole.com
SMTP_FROM_NAME=StealthRole

# URLs
APP_BASE_URL=https://stealthrole.com
FRONTEND_URL=https://stealthrole.com
ALLOWED_ORIGINS=https://stealthrole.com,https://www.stealthrole.com

# Sentry
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production

# Optional (enhances signals)
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
JSEARCH_API_KEY=
```

---

## Step 3: Fix Production Compose (add Celery Beat)

The current `docker-compose.prod.yml` is missing the `beat` service. Add it:

```yaml
  # Add after worker_rendering service:
  beat:
    <<: *worker-base
    command: celery -A app.workers.celery_app.celery beat --loglevel=info
    # Only 1 beat instance should ever run
    deploy:
      replicas: 1
```

---

## Step 4: Fix Frontend API Proxy

Update `frontend/next.config.js` — change the API rewrite from `localhost:8000` to the docker service name:

```javascript
// For production (behind nginx), rewrite to the api container:
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://api:8000/api/:path*',
    },
  ];
},
```

Or better — serve frontend as static files via nginx and proxy `/api/*` to the API container.

---

## Step 5: Build Frontend

```bash
cd /opt/stealthrole/frontend
npm install
NEXT_PUBLIC_API_URL="" npm run build
# Output in .next/ or out/ depending on config
```

If using nginx to serve static:
```bash
npx next export  # generates /out directory
# OR copy .next/static and public/ to nginx volume
```

---

## Step 6: SSL Certificate

```bash
cd /opt/stealthrole

# Start nginx on HTTP first
docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d nginx

# Get certificate
docker compose -f docker/docker-compose.prod.yml --env-file .env.production run --rm certbot \
  certbot certonly --webroot \
  -w /var/www/certbot \
  -d stealthrole.com -d www.stealthrole.com \
  --email admin@stealthrole.com \
  --agree-tos --no-eff-email

# Restart nginx with SSL
docker compose -f docker/docker-compose.prod.yml --env-file .env.production restart nginx
```

---

## Step 7: Run Migrations

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production run --rm migrator
```

---

## Step 8: Deploy All Services

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

Check everything is running:
```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
```

Expected:
```
NAME                STATUS
api                 Up (healthy)
worker_default      Up
worker_llm          Up
worker_rendering    Up
beat                Up
postgres            Up (healthy)
redis               Up (healthy)
nginx               Up
certbot             Up
```

---

## Step 9: Configure Webhooks

### Stripe
1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://stealthrole.com/api/v1/billing/webhook`
3. Events: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`
4. Copy signing secret → `STRIPE_WEBHOOK_SECRET`

### Twilio WhatsApp (when production number is approved)
1. Twilio Console → Messaging → WhatsApp → Sandbox Settings (or Senders)
2. "When a message comes in" URL: `https://stealthrole.com/api/v1/whatsapp/webhook`
3. Method: POST

### Google OAuth Redirect
1. Google Cloud Console → Credentials → OAuth 2.0 Client
2. Add authorized redirect URI: `https://stealthrole.com/api/v1/email-integration/callback`

---

## Step 10: Verify Deployment

```bash
# Health
curl https://stealthrole.com/health

# Create admin account
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api python3 -c "
from app.services.auth.auth_service import create_user
import asyncio
asyncio.run(create_user('admin@stealthrole.com', 'YourPassword', 'Admin'))
"

# Full API regression test
TOKEN=$(curl -s https://stealthrole.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@stealthrole.com","password":"YourPassword"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

ENDPOINTS=(
  /health /api/v1/auth/me /api/v1/dashboard/summary
  /api/v1/applications/board /api/v1/applications/analytics
  /api/v1/profiles/active /api/v1/scout/signals
  /api/v1/scout/hidden-market /api/v1/scout/predictions
  /api/v1/opportunities/radar /api/v1/crm/summary
  /api/v1/linkedin/stats /api/v1/credits/balance
  /api/v1/billing/plans /api/v1/billing/status
  /api/v1/email-intelligence/report
)

PASS=0; FAIL=0
for ep in "${ENDPOINTS[@]}"; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://stealthrole.com${ep}" \
    -H "Authorization: Bearer $TOKEN")
  if [ "$CODE" -ge 200 ] && [ "$CODE" -lt 300 ]; then
    echo "✅ $CODE $ep"; ((PASS++))
  else
    echo "❌ $CODE $ep"; ((FAIL++))
  fi
done
echo "TOTAL: $((PASS+FAIL)) | PASS: $PASS | FAIL: $FAIL"

# Verify Celery Beat is scheduling tasks
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  logs beat --tail 10

# Verify workers are alive
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec worker_default celery -A app.workers.celery_app.celery inspect ping
```

---

## Step 11: Set Up Monitoring

### Cron: Daily DB Backup
```bash
# /etc/cron.daily/stealthrole-backup
#!/bin/bash
docker exec stealthrole_postgres pg_dump -U stealthrole stealthrole \
  | gzip > /backups/stealthrole-$(date +%Y%m%d).sql.gz
find /backups -name "stealthrole-*.sql.gz" -mtime +30 -delete
```

### UptimeRobot / Better Uptime
- Monitor: `https://stealthrole.com/health`
- Alert on non-200

### Log Monitoring
```bash
# All services
docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs -f

# LLM costs
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  logs worker_llm 2>&1 | grep cost_usd
```

---

## Updating (Zero-Downtime)

```bash
cd /opt/stealthrole
git pull origin main

# Rebuild + restart services one at a time
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --no-deps --build api

docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --no-deps --build worker_default worker_llm worker_rendering beat

# Run new migrations if any
docker compose -f docker/docker-compose.prod.yml --env-file .env.production run --rm migrator
```

---

## Scaling

| Bottleneck | Solution |
|-----------|----------|
| API throughput | Increase uvicorn workers or add API replicas behind nginx |
| LLM throughput | Increase `worker_llm` concurrency (watch Anthropic rate limits) |
| Database | Move to managed PostgreSQL (RDS/Supabase) |
| Redis | Move to managed Redis (ElastiCache/Upstash) |
| Storage | S3 handles scale automatically |

---

## Cost Estimate (100 active users/month)

| Service | Estimated Cost |
|---------|---------------|
| VPS (4 vCPU, 8GB) | $40-80/month |
| Anthropic (Claude) | $50-200/month (~$0.30/pack × packs generated) |
| Serper | $50/month (50K queries) |
| Twilio WhatsApp | $0.005-0.05/message × volume |
| S3 | $5-10/month |
| Domain + SSL | Free (Let's Encrypt) |
| Sentry | Free tier or $26/month |
| SMTP (Resend) | Free tier (3K emails/month) |
| **Total** | **~$150-400/month** |
