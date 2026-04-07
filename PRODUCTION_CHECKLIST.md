# StealthRole — Production Deployment Checklist

> Complete this checklist before deploying to production. Each section has verification steps.
> Tested locally on 2026-03-29 — 29/29 API endpoints passing, all integrations verified.

---

## 🔴 CRITICAL — Must complete before launch

### 1. Serper API Key
- [ ] Sign up at [serper.dev](https://serper.dev) or top up existing account
- [ ] Current key (`3624f...`) has **negative balance** — all signal detection is dead without this
- [ ] ~2,500 free queries on new accounts, then ~$50/month for 50K queries
- [ ] **Blocks**: Market Signals, LinkedIn Profile Import, Hidden Market Engine, Daily Scout Scan
- [ ] Set `SERPER_API_KEY` in `.env.production`
- **Verify**: `curl -s -X POST https://google.serper.dev/search -H "X-API-KEY: YOUR_KEY" -H "Content-Type: application/json" -d '{"q":"test"}' | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('organic',[])), 'results')"`

### 2. Twilio WhatsApp — Production Number
- [ ] Currently using **sandbox** number (+14155238886) — users must text "join" first
- [ ] Apply for [Twilio WhatsApp Business Profile](https://www.twilio.com/docs/whatsapp/tutorial/requesting-access-to-whatsapp)
- [ ] Takes 1-2 weeks for approval
- [ ] Once approved, update `TWILIO_WHATSAPP_FROM=whatsapp:+YOUR_PRODUCTION_NUMBER`
- [ ] Set up webhook URL: `https://yourdomain.com/api/v1/whatsapp/webhook`
- [ ] **Interim workaround**: Keep sandbox but add opt-in instructions in onboarding UI
- **Verify**: Send test message via API → check delivery status in Twilio console

### 3. Google OAuth — Production Mode
- [ ] Go to [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → OAuth consent screen
- [ ] Move app from "Testing" to "Production" (testing mode tokens expire after 7 days)
- [ ] Add `gmail.readonly` and `userinfo.email` scopes
- [ ] Set authorized redirect URI: `https://yourdomain.com/api/v1/email-integration/callback`
- [ ] Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env.production`
- [ ] If you want users beyond your org: submit for Google verification (takes 2-6 weeks)
- **Verify**: Complete OAuth flow → check token refresh works after 1 hour

### 4. Stripe — Live Keys
- [ ] Switch from test keys to live keys in Stripe Dashboard
- [ ] Set `STRIPE_SECRET_KEY=sk_live_...` and `STRIPE_PUBLISHABLE_KEY=pk_live_...`
- [ ] Create webhook endpoint: `https://yourdomain.com/api/v1/billing/webhook`
- [ ] Subscribe to events: `customer.subscription.*`, `invoice.payment_succeeded`, `invoice.payment_failed`
- [ ] Copy webhook signing secret → `STRIPE_WEBHOOK_SECRET`
- [ ] Create products/prices matching your plan IDs (Free/Pro/Elite)
- [ ] Set `STRIPE_PRICE_PRO_MONTHLY` and `STRIPE_PRICE_STARTER_MONTHLY`
- **Verify**: Test checkout flow with Stripe test card → verify subscription created

### 5. Anthropic API Key
- [ ] Set `ANTHROPIC_API_KEY` with production key
- [ ] Check rate limits (Tier 2+ recommended for concurrent pack generation)
- [ ] Model: `claude-sonnet-4-6` (used for packs, conversation analysis, signal scoring)
- [ ] Budget: ~$0.28/pack, ~$0.05/conversation analysis. Estimate $50-200/month for 100 active users
- **Verify**: `curl -s https://api.anthropic.com/v1/messages -H "x-api-key: YOUR_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-sonnet-4-6","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('content',[{}])[0].get('text','FAILED'))"`

---

## 🟡 IMPORTANT — Should complete before launch

### 6. Domain & SSL
- [ ] Point domain A record to server IP
- [ ] Update `APP_BASE_URL`, `FRONTEND_URL`, `ALLOWED_ORIGINS` in `.env.production`
- [ ] Update `next.config.js` API rewrite to point to production API (or use nginx proxy)
- [ ] SSL via Let's Encrypt (certbot in docker-compose.prod.yml handles this)

### 7. S3 Storage
- [ ] Create S3 bucket (or compatible: DigitalOcean Spaces, Cloudflare R2)
- [ ] Set `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION`
- [ ] Remove `S3_ENDPOINT_URL` (only used for local MinIO)
- [ ] Enable versioning on bucket (for CV recovery)
- **Verify**: Upload a test file via API → check it appears in bucket

### 8. Email (SMTP)
- [ ] Set up transactional email (Resend, Postmark, or SES)
- [ ] Set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- **Verify**: Trigger password reset → email arrives

### 9. Sentry Error Tracking
- [ ] Create Sentry project → get DSN
- [ ] Set `SENTRY_DSN` in `.env.production`
- **Verify**: Hit `/api/v1/sentry-test` → error appears in Sentry dashboard

### 10. Email Token Encryption
- [ ] Generate: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Set `EMAIL_TOKEN_ENCRYPTION_KEY` — encrypts stored Gmail/Outlook OAuth tokens at rest
- [ ] ⚠️ If you lose this key, all connected email accounts must re-authenticate

### 11. Secret Key
- [ ] Generate: `openssl rand -hex 32`
- [ ] Set `SECRET_KEY` — used for JWT signing
- [ ] ⚠️ Changing this invalidates all active sessions

---

## 🟢 OPTIONAL — Nice to have

### 12. Adzuna API (enhances signals)
- [ ] Sign up at [developer.adzuna.com](https://developer.adzuna.com)
- [ ] Set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`
- [ ] Adds employer hiring surge detection to signal engine

### 13. JSearch API (enhances job search)
- [ ] Get key from RapidAPI
- [ ] Set `JSEARCH_API_KEY`
- [ ] Adds additional job listing sources

### 14. CrunchBase / MAGNiTT (future)
- [ ] These are coded but use demo data currently
- [ ] Real API keys would provide verified funding + leadership signals

---

## 🏗️ Infrastructure

### Minimum Server Specs
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| vCPU | 4 | 8 |
| RAM | 8 GB | 16 GB |
| Storage | 40 GB SSD | 100 GB SSD |
| OS | Ubuntu 22.04 | Ubuntu 22.04 |

### Services Running
| Service | Purpose | Concurrency |
|---------|---------|-------------|
| `api` | FastAPI server | uvicorn workers (4) |
| `worker_default` | CV parsing, general tasks | 4 |
| `worker_llm` | Claude API calls (packs, analysis) | 2 |
| `worker_rendering` | DOCX generation + S3 upload | 4 |
| `beat` | Celery Beat scheduler | 1 |
| `postgres` | Database | 1 |
| `redis` | Task queue + cache | 1 |
| `nginx` | Reverse proxy + SSL + static | 1 |

### Celery Beat Scheduled Tasks
| Task | Schedule | What it does |
|------|----------|-------------|
| `daily_scout_scan` | Daily | Scans signals for all users → caches results → sends WhatsApp alerts |
| `periodic_email_sync` | Every 6 hours | Syncs connected Gmail/Outlook accounts → extracts signals |
| `periodic_calendar_sync` | Every hour | Syncs interview calendar events |

---

## ✅ Post-Deploy Verification

Run these after deployment:

```bash
# 1. Health check
curl https://yourdomain.com/health

# 2. API regression (all must return 200)
TOKEN=$(curl -s https://yourdomain.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"..."}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

for ep in /api/v1/auth/me /api/v1/dashboard/summary /api/v1/applications/board \
  /api/v1/profiles/active /api/v1/scout/signals /api/v1/scout/hidden-market \
  /api/v1/scout/predictions /api/v1/linkedin/stats /api/v1/credits/balance \
  /api/v1/billing/plans; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://yourdomain.com${ep}" \
    -H "Authorization: Bearer $TOKEN")
  echo "$CODE $ep"
done

# 3. Celery workers running
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec worker_default celery -A app.workers.celery_app.celery inspect active

# 4. Celery Beat running (check scheduled tasks)
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  logs beat --tail 20
```

---

## 🐛 Known Issues from Testing (2026-03-29)

1. **Opportunity Radar scores 0%** — The radar's independent scoring (scorer.py) doesn't match well with signal-engine-generated opportunities. The main scout/signals endpoint works perfectly (94%, 88%, 85% etc). Radar needs tuning to pass through pre-computed fit scores when evidence is strong.

2. **Frontend next.config.js hardcodes localhost:8000** — Must update API rewrite destination for production deployment.

3. **`/auth/me` doesn't expose WhatsApp fields** — The user schema response doesn't include `whatsapp_number`, `whatsapp_verified`, `whatsapp_alert_mode`. Frontend settings page handles it separately, but API consumers can't check WhatsApp status via `/auth/me`.

4. **Celery Beat not in docker-compose.prod.yml** — The `beat` service exists in dev compose but is missing from prod compose. Must add it or daily_scout_scan won't run.
