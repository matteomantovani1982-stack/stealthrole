# StealthRole — Testing Playbook

Full end-to-end testing guide. Follow flows in exact order.

---

## STEP 0 — Start the Stack

```bash
# From project root
make up
# Wait for all services to be healthy (~30 seconds)
# Watch logs for "Application startup complete"
make logs s=api
```

**Verify stack is running:**

```bash
curl http://localhost:8000/health
```

**Expected:**
```json
{"status": "healthy"}
```

```bash
curl http://localhost:8000/health/ready
```

**Expected:**
```json
{"status": "ready", "database": "ok", "redis": "ok"}
```

If either fails, check `make logs` for errors. Common issues:
- PostgreSQL not ready yet → wait 10 more seconds
- Migration failed → `make migrate` then `make restart`
- Port 8000 in use → `make down` then `make up`

**Base URL for all tests:** `http://localhost:8000`

---

## FLOW 1 — Normal Account (Auth)

### 1.1 Register

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@stealthrole.com",
    "password": "TestPass123!",
    "full_name": "Test User"
  }' | python3 -m json.tool
```

**Expected (201):**
```json
{
  "user": {
    "id": "<uuid>",
    "email": "test@stealthrole.com",
    "full_name": "Test User",
    "is_active": true,
    "is_verified": false,
    "whatsapp_number": null,
    "whatsapp_verified": false,
    "whatsapp_alert_mode": null,
    "notification_preferences": null,
    "created_at": "<timestamp>"
  },
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

**Save the tokens:**
```bash
export ACCESS_TOKEN="<paste access_token from response>"
export REFRESH_TOKEN="<paste refresh_token from response>"
```

**Error cases to verify:**
```bash
# Duplicate email → 409
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@stealthrole.com", "password": "TestPass123!"}' \
  | python3 -m json.tool
# Expected: 409 "Email already registered"

# Short password → 422
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "new@test.com", "password": "short"}' \
  | python3 -m json.tool
# Expected: 422 validation error (min_length 8)
```

### 1.2 Login

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@stealthrole.com",
    "password": "TestPass123!"
  }' | python3 -m json.tool
```

**Expected (200):**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Update tokens:**
```bash
export ACCESS_TOKEN="<new access_token>"
export REFRESH_TOKEN="<new refresh_token>"
```

**Error cases:**
```bash
# Wrong password → 401
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@stealthrole.com", "password": "WrongPass"}' \
  | python3 -m json.tool
# Expected: 401 "Invalid credentials"

# Unknown email → 401
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "nobody@test.com", "password": "TestPass123!"}' \
  | python3 -m json.tool
# Expected: 401 "Invalid credentials"
```

### 1.3 Verify Token (Get Profile)

```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):** Same `UserResponse` as registration.

**Error case:**
```bash
# No token → 401
curl -s http://localhost:8000/api/v1/auth/me \
  | python3 -m json.tool
# Expected: 401

# Garbage token → 401
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer garbage" \
  | python3 -m json.tool
# Expected: 401
```

### 1.4 Refresh Token

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "access_token": "<new jwt>",
  "refresh_token": "<new jwt>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**IMPORTANT:** Update both tokens. Old refresh token is now invalid (rotation).

```bash
export ACCESS_TOKEN="<new access_token>"
export REFRESH_TOKEN="<new refresh_token>"
```

**Error case:**
```bash
# Reuse old refresh token → 401 (rotation prevents reuse)
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "old-token-from-before-refresh"}' \
  | python3 -m json.tool
# Expected: 401
```

### 1.5 Logout

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{"message": "Logged out"}
```

**Verify logout worked:**
```bash
# Same token should now be rejected
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
# Expected: 401
```

**Re-login for remaining tests:**
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@stealthrole.com", "password": "TestPass123!"}' \
  | python3 -m json.tool

# Update tokens:
export ACCESS_TOKEN="<new access_token>"
export REFRESH_TOKEN="<new refresh_token>"
```

### FLOW 1 — Checklist

- [ ] Register → 201, tokens returned
- [ ] Duplicate register → 409
- [ ] Login → 200, tokens + expires_in
- [ ] Wrong password → 401
- [ ] GET /me with token → 200
- [ ] GET /me without token → 401
- [ ] Refresh → 200, new token pair
- [ ] Old refresh token rejected → 401
- [ ] Logout → 200
- [ ] Token rejected after logout → 401

---

## FLOW 2 — Google Login

### Status: TESTABLE ONLY WITH GOOGLE CLOUD CREDENTIALS

### 2.1 Required Environment Variables

```bash
# In your .env file:
GOOGLE_CLIENT_ID=<your-google-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
```

These come from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID.

**Authorized redirect URI in Google Console must include:**
```
http://localhost:3000/auth/callback
```

### 2.2 Get Google Auth URL

```bash
curl -s http://localhost:8000/api/v1/auth/google/url \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=http://localhost:3000/auth/callback&response_type=code&scope=email%20profile&access_type=offline"
}
```

**If GOOGLE_CLIENT_ID is not set:** The URL will contain `None` as client_id and the Google redirect will fail.

### 2.3 Complete Google Login

This is a two-step browser flow:
1. User visits the URL from step 2.2
2. Google redirects to `http://localhost:3000/auth/callback?code=<auth-code>`
3. Frontend sends the code to the backend:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/google \
  -H "Content-Type: application/json" \
  -d '{"code": "<auth-code-from-google-redirect>"}' \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 2.4 Without Credentials

If `GOOGLE_CLIENT_ID` is not set:
- `GET /api/v1/auth/google/url` returns a URL with `None` → useless but not an error
- `POST /api/v1/auth/google` with a code → will fail when exchanging with Google (network error or 401 from Google)

**Bottom line:** Not testable without credentials. Skip to Flow 3.

### FLOW 2 — Checklist

- [ ] GOOGLE_CLIENT_ID set? If no → skip this flow
- [ ] GET /google/url → returns valid Google OAuth URL
- [ ] Open URL in browser → Google consent screen loads
- [ ] After consent → redirected to localhost:3000/auth/callback
- [ ] POST /google with code → 200, tokens returned
- [ ] GET /me → shows Google user email
- [ ] Password change blocked for Google-only user → 403

---

## FLOW 3 — Quick Start

**Prerequisite:** Authenticated (have `$ACCESS_TOKEN` from Flow 1).

All quick-start tests hit: `POST /api/v1/quick-start`

### 3.1 Minimal — Target Role Only

```bash
curl -s -X POST http://localhost:8000/api/v1/quick-start \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_role": "Senior Backend Engineer"
  }' | python3 -m json.tool
```

**Expected (200):**
```json
{
  "user_id": "<uuid>",
  "computed_at": "<iso-timestamp>",
  "signals": [],
  "actions": [],
  "summary": {
    "total_signals": 0,
    "total_actions": 0,
    "top_company": null,
    "recommended_action": null,
    "target_role": "Senior Backend Engineer",
    "next_steps": ["Upload your CV to get started", "Add target companies to track"]
  }
}
```

**Note:** Signals and actions will be empty on a fresh account with no data. This is correct — the engine returns the empty result when no signals exist.

### 3.2 With CV Text

```bash
curl -s -X POST http://localhost:8000/api/v1/quick-start \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Senior Python developer with 8 years experience in fintech. Built payment systems at Stripe and Revolut. Expert in FastAPI, PostgreSQL, Redis, AWS. Previously at Goldman Sachs.",
    "target_role": "Staff Engineer"
  }' | python3 -m json.tool
```

**Expected (200):** Same structure. Signals/actions empty on fresh account. Once signals exist (after Flow 4/5), re-run this and verify that signals matching "fintech", "python", "payment" rank higher.

### 3.3 With LinkedIn URL

```bash
curl -s -X POST http://localhost:8000/api/v1/quick-start \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "linkedin_url": "https://www.linkedin.com/in/john-doe-backend-engineer-fintech"
  }' | python3 -m json.tool
```

**Expected (200):** Same structure. Keywords extracted from URL slug: "john", "doe", "backend", "engineer", "fintech".

### 3.4 With Target Companies

```bash
curl -s -X POST http://localhost:8000/api/v1/quick-start \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_role": "Backend Engineer",
    "target_companies": ["Google", "Stripe", "Revolut"]
  }' | python3 -m json.tool
```

**Expected (200):** Same structure. If signals for Google/Stripe/Revolut exist, they appear in results filtered by company.

### 3.5 No Auth → 401

```bash
curl -s -X POST http://localhost:8000/api/v1/quick-start \
  -H "Content-Type: application/json" \
  -d '{"target_role": "Engineer"}' \
  | python3 -m json.tool
```

**Expected: 401**

### FLOW 3 — Checklist

- [ ] Role only → 200, empty signals (fresh account)
- [ ] CV text → 200, keywords logged (check `make logs s=api` for `quick_start_keywords`)
- [ ] LinkedIn URL → 200
- [ ] Target companies → 200
- [ ] No auth → 401
- [ ] After creating signals (Flow 4), re-test → signals appear ranked by relevance

---

## FLOW 4 — Extension Capture

### 4.1 Extension Frontend — Does It Exist?

**Yes.** Located at: `extension/`

```
extension/
  manifest.json          — Manifest V3
  icons/                 — Extension icons
  src/
    background.js        — Service worker
    popup.html / popup.js — Extension popup UI
    config.js            — API base URL config
    token-sync.js        — Auth token sync with main app
    linkedin-core.js     — LinkedIn DOM utilities
    linkedin-profile.js  — Profile scraping
    linkedin-jobs.js     — Job scraping
    linkedin-messages.js — Message capture
    linkedin-connections.js
    linkedin-intelligence.js
    linkedin-search.js
    linkedin-composer.js
    autofill.js
    overlay.css
```

### 4.2 Loading the Extension in Chrome

1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode" (top-right toggle)
3. Click "Load unpacked"
4. Select the `extension/` folder in the project root
5. Extension icon appears in toolbar

### 4.3 Connecting to Backend

The extension reads the API URL from `extension/src/config.js`. Default is `http://localhost:8000`.

**Token sync:** The extension shares auth tokens with the main app via `token-sync.js`. After logging in through the frontend (`http://localhost:3000`), the extension picks up the token from the shared storage.

**For API-only testing (no frontend):** You can test the capture endpoints directly with curl, which is what we do below.

### 4.4 Capture Profile (via curl)

```bash
curl -s -X POST http://localhost:8000/api/v1/extension/capture-profile \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "linkedin_url": "https://www.linkedin.com/in/janedoe",
    "full_name": "Jane Doe",
    "headline": "VP of Engineering at Stripe — Hiring for Backend",
    "company": "Stripe",
    "location": "London, UK"
  }' | python3 -m json.tool
```

**Expected (201):**
```json
{
  "success": true,
  "capture_id": "<uuid>",
  "capture_type": "profile",
  "signals_created": 1,
  "message": "Profile captured — signal created"
}
```

**Why `signals_created: 1`?** The headline contains "VP" (hiring keyword), so a `leadership` signal is created for Stripe.

**Pipeline runs:** Check logs for quality + interpretation:
```bash
make logs s=api 2>&1 | grep "extension_profile_pipeline"
```
Expected log entry showing `quality_gate` and `interpreted` fields.

**Non-hiring profile (no signal):**
```bash
curl -s -X POST http://localhost:8000/api/v1/extension/capture-profile \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "linkedin_url": "https://www.linkedin.com/in/bobsmith",
    "full_name": "Bob Smith",
    "headline": "Software Engineer at Google",
    "company": "Google",
    "location": "NYC"
  }' | python3 -m json.tool
```

**Expected (201):**
```json
{
  "success": true,
  "capture_id": "<uuid>",
  "capture_type": "profile",
  "signals_created": 0,
  "message": "Profile captured"
}
```

### 4.5 Capture Job

```bash
curl -s -X POST http://localhost:8000/api/v1/extension/capture-job \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://www.linkedin.com/jobs/view/123456",
    "title": "Senior Backend Engineer",
    "company": "Revolut",
    "location": "London, Remote",
    "description": "We are looking for a Senior Backend Engineer to join our payments team. Python, FastAPI, PostgreSQL required."
  }' | python3 -m json.tool
```

**Expected (201):**
```json
{
  "success": true,
  "capture_id": "<uuid>",
  "capture_type": "job",
  "signals_created": 1,
  "message": "Job posting captured — signal created"
}
```

Always creates a `hiring_surge` signal. Pipeline runs inline.

### 4.6 Capture Company

```bash
curl -s -X POST http://localhost:8000/api/v1/extension/capture-company \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_url": "https://www.linkedin.com/company/monzo",
    "company_name": "Monzo",
    "industry": "Fintech",
    "size": "1001-5000",
    "description": "Digital bank",
    "recent_posts": [{"text": "We just raised Series G!"}]
  }' | python3 -m json.tool
```

**Expected (201):**
```json
{
  "success": true,
  "capture_id": "<uuid>",
  "capture_type": "company",
  "signals_created": 1,
  "message": "Company page captured — signal created"
}
```

Creates an `expansion` signal for Monzo. Pipeline runs inline.

### 4.7 Plan Gating on Extension (FREE Plan)

Extension capture requires Starter plan or higher. On a FREE plan:

```bash
curl -s -X POST http://localhost:8000/api/v1/extension/capture-job \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"job_url": "https://example.com/job", "title": "Test", "company": "Test"}' \
  | python3 -m json.tool
```

**Expected (403):**
```json
{"detail": "Extension capture requires Starter plan or higher."}
```

**Note:** If you get 201 instead of 403, the test user may already be on a paid plan. See Flow 7 for how to verify/change plan tier.

### 4.8 Rate Limiting

Fire 31 requests in quick succession:
```bash
for i in $(seq 1 31); do
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}" -X POST \
    http://localhost:8000/api/v1/extension/capture-job \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"job_url": "https://example.com/job", "title": "Test", "company": "Test"}'
  echo ""
done
```

**Expected:** First 30 return 201 (or 403 if FREE plan). Request 31 returns **429 Too Many Requests**.

### FLOW 4 — Checklist

- [ ] Extension files exist at `extension/`
- [ ] Profile capture (hiring headline) → 201, signals_created: 1
- [ ] Profile capture (non-hiring) → 201, signals_created: 0
- [ ] Job capture → 201, signals_created: 1
- [ ] Company capture → 201, signals_created: 1
- [ ] Pipeline logs show quality_gate + interpreted
- [ ] No auth → 401
- [ ] FREE plan → 403 (if applicable)
- [ ] Rate limit → 429 after 30 req/min

---

## FLOW 5 — Signal to Action Pipeline

**Prerequisite:** Have signals from Flow 4 (at least one capture with `signals_created: 1`).

### 5.1 Find Your Signal ID

The signal was created during capture. Get it from the signals list:

```bash
curl -s http://localhost:8000/api/v1/scout/signals \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

Look for the signal created during capture. Copy its `id` field.

```bash
export SIGNAL_ID="<paste signal id>"
```

**Alternative — direct DB query (if endpoint not available):**
```bash
make psql
# Inside psql:
SELECT id, company_name, signal_type, confidence, quality_gate_result
FROM hidden_signals
ORDER BY created_at DESC LIMIT 5;
```

### 5.2 Generate Actions for Signal

```bash
curl -s -X POST http://localhost:8000/api/v1/actions/generate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"signal_id\": \"$SIGNAL_ID\",
    \"profile_fit\": 0.70,
    \"access_strength\": 0.60
  }" | python3 -m json.tool
```

**Expected (201):**
```json
{
  "actions_created": 2,
  "signal_id": "<uuid>",
  "action_types": ["linkedin_outreach", "email_outreach"]
}
```

**Possible `actions_created` values:** 0–4 depending on decision score thresholds.
- `linkedin_outreach` generated if composite score >= 0.40
- `email_outreach` generated if composite score >= 0.50
- `referral_request` generated if access_strength >= 0.60
- `follow_up` generated if urgency+timing >= 0.45

If you get 0 actions, increase `profile_fit` and `access_strength` to 0.90.

**Error cases:**
```bash
# Non-existent signal → 404
curl -s -X POST http://localhost:8000/api/v1/actions/generate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"signal_id": "00000000-0000-0000-0000-000000000000"}' \
  | python3 -m json.tool
# Expected: 404 "Signal not found"

# No auth → 401
curl -s -X POST http://localhost:8000/api/v1/actions/generate \
  -H "Content-Type: application/json" \
  -d "{\"signal_id\": \"$SIGNAL_ID\"}" \
  | python3 -m json.tool
# Expected: 401
```

### 5.3 List Actions

```bash
curl -s http://localhost:8000/api/v1/actions \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "actions": [
    {
      "id": "<uuid>",
      "action_type": "linkedin_outreach",
      "status": "generated",
      "target_name": "...",
      "target_company": "Stripe",
      "reason": "...",
      "message_subject": "...",
      "message_body": "...",
      "timing_label": "this_week",
      "confidence": 0.65,
      "priority": 1,
      "decision_score": 0.72,
      "channel_metadata": {},
      "is_user_edited": false,
      "created_at": "<timestamp>",
      "expires_at": "<timestamp>"
    }
  ],
  "total": 2
}
```

Save an action ID:
```bash
export ACTION_ID="<paste first action id>"
```

### 5.4 Get Top Actions

```bash
curl -s http://localhost:8000/api/v1/actions/top \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "actions": [...],
  "total": 2,
  "active_signals": 3
}
```

### 5.5 Transition Action: Queue

```bash
curl -s -X PATCH "http://localhost:8000/api/v1/actions/$ACTION_ID/queue" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "id": "<uuid>",
  "status": "queued",
  "previous_status": "generated",
  "success": true
}
```

### 5.6 Edit Action Message

```bash
curl -s -X PATCH "http://localhost:8000/api/v1/actions/$ACTION_ID/message" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message_subject": "Quick question about your team",
    "message_body": "Hi Jane, I noticed Stripe is expanding the payments team..."
  }' | python3 -m json.tool
```

**Expected (200):** Full `ActionItem` with `is_user_edited: true` and updated message.

### 5.7 Transition: Mark Sent

```bash
curl -s -X PATCH "http://localhost:8000/api/v1/actions/$ACTION_ID/sent" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):** `status: "sent"`

### 5.8 Transition: Mark Responded

```bash
curl -s -X PATCH "http://localhost:8000/api/v1/actions/$ACTION_ID/responded" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):** `status: "responded"`

### 5.9 Execute Action (Mock)

Use a different action (one still in `generated` or `queued` status):

```bash
# Get another action ID from the list
export ACTION_ID_2="<another action id>"

curl -s -X POST "http://localhost:8000/api/v1/actions/$ACTION_ID_2/execute" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "success": true,
  "channel": "linkedin",
  "mock": true,
  "message": "LinkedIn message queued (mock — extension integration pending)",
  "action_id": "<uuid>"
}
```

**`mock: true` is expected.** Real channel integrations are not wired yet.

### 5.10 Dismiss Action

```bash
# Use a generated action (not yet queued/sent)
curl -s -X PATCH "http://localhost:8000/api/v1/actions/$ACTION_ID_2/dismiss" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):** `status: "dismissed"`

### 5.11 Invalid Transitions

```bash
# Try to queue an already-sent action → 400
curl -s -X PATCH "http://localhost:8000/api/v1/actions/$ACTION_ID/queue" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
# Expected: 400 "Cannot queue this action (not found or invalid transition)"
```

### FLOW 5 — Checklist

- [ ] Generate actions for signal → 201, actions_created >= 1
- [ ] List actions → 200, shows generated actions
- [ ] Top actions → 200, includes active_signals count
- [ ] Queue action → 200, status: "queued"
- [ ] Edit message → 200, is_user_edited: true
- [ ] Mark sent → 200, status: "sent"
- [ ] Mark responded → 200, status: "responded"
- [ ] Execute (mock) → 200, mock: true
- [ ] Dismiss → 200, status: "dismissed"
- [ ] Invalid transition → 400
- [ ] Fake signal ID → 404

---

## FLOW 6 — Insights / Value Engine

### 6.1 Get Insights

```bash
curl -s http://localhost:8000/api/v1/insights \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):**
```json
{
  "user_id": "<uuid>",
  "computed_at": "<timestamp>",
  "signal_effectiveness": { ... },
  "action_effectiveness": { ... },
  "path_performance": { ... },
  "timing_insights": { ... },
  "summary": "...",
  "recommendations": [ ... ]
}
```

On a fresh account with few signals/actions, most metrics will be zero or minimal. This is correct.

### 6.2 Plan Gating

Insights require **Starter plan or higher**. On FREE plan:

**Expected (403):**
```json
{"detail": "Value insights require Starter plan or higher."}
```

### 6.3 Re-test After Flow 5

After generating and transitioning actions in Flow 5, re-run the insights endpoint. You should see non-zero `action_effectiveness` and updated `recommendations`.

### FLOW 6 — Checklist

- [ ] GET /insights → 200 (on paid plan) or 403 (FREE)
- [ ] Response contains all sections (signal_effectiveness, action_effectiveness, etc.)
- [ ] After creating actions → metrics are populated

---

## FLOW 7 — Plan Gating

### 7.1 Check Current Plan

```bash
curl -s http://localhost:8000/api/v1/billing/status \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool
```

**Expected (200):** Shows `plan_tier`, `credits_remaining`, subscription status.

### 7.2 Grant Credits / Upgrade Plan (Dev Mode)

If you're on FREE and need to test paid features:

```bash
# Grant credits (dev endpoint — requires admin or DEMO_MODE)
curl -s -X POST http://localhost:8000/api/v1/dev/grant-credits \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 100}' \
  | python3 -m json.tool
```

**To change plan tier directly (via psql):**
```bash
make psql
```
```sql
-- Find user
SELECT id, email FROM users WHERE email = 'test@stealthrole.com';

-- Check subscription
SELECT * FROM subscriptions WHERE user_id = '<user-id>';

-- Update to PRO (if subscription exists)
UPDATE subscriptions SET plan_tier = 'pro' WHERE user_id = '<user-id>';

-- Or insert if no subscription row exists
INSERT INTO subscriptions (id, user_id, plan_tier, status, created_at, updated_at)
VALUES (gen_random_uuid(), '<user-id>', 'pro', 'active', now(), now());
```

### 7.3 Test FREE Limits

With user on FREE plan:

| Feature | Limit | Endpoint | Expected |
|---------|-------|----------|----------|
| Actions/month | 5 | POST /actions/generate | 429 after 5 |
| Quick-start/day | 1 | POST /quick-start | Soft limit (returns limit in response) |
| Value insights | Blocked | GET /insights | 403 |
| Extension capture | Blocked | POST /extension/capture-* | 403 |

**Test action quota exhaustion:**
```bash
# Generate actions for 5 different signals (or same signal 5 times if it creates 1 action each)
# On the 6th attempt:
curl -s -X POST http://localhost:8000/api/v1/actions/generate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"signal_id\": \"$SIGNAL_ID\"}" \
  | python3 -m json.tool
```

**Expected (429):**
```json
{"detail": "Monthly action quota exceeded: 5/5 actions used on free plan. Upgrade for more."}
```

**Response headers include:**
```
X-Quota-Used: 5
X-Quota-Limit: 5
```

### 7.4 Test PRO Limits

With user on PRO plan:

| Feature | Limit | Expected |
|---------|-------|----------|
| Actions/month | 100 | Works until 100 |
| Quick-start/day | Unlimited | Always works |
| Value insights | Allowed | 200 |
| Extension capture | Allowed | 201 |

### 7.5 Test UNLIMITED

With user on UNLIMITED plan: All features, no caps, no quotas.

### FLOW 7 — Checklist

- [ ] GET /billing/status → shows current plan
- [ ] FREE: actions generate → 429 after 5/month
- [ ] FREE: extension capture → 403
- [ ] FREE: insights → 403
- [ ] PRO: all features work within limits
- [ ] UNLIMITED: no restrictions
- [ ] 429 response includes X-Quota-Used and X-Quota-Limit headers

---

## FLOW 8 — Messaging Integrations Status

### 8.1 Gmail

| What | Status | How to Test |
|------|--------|-------------|
| OAuth connect | **Built** | Set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` in `.env`. Hit `GET /api/v1/email/connect/google`. |
| Email scan | **Built** | After OAuth: `POST /api/v1/email/scan` |
| Send email | **Mock only** | `ActionExecutor._send_email()` returns `mock: true`. No real send. |
| Calendar sync | **Built** | After OAuth: calendar sync Celery task runs |

**Without credentials:** Not testable. OAuth flow will fail at token exchange.

### 8.2 Outlook

| What | Status | How to Test |
|------|--------|-------------|
| OAuth connect | **Built** | Requires Azure AD app registration + client credentials |
| Email scan | **Built** | After OAuth: uses Microsoft Graph API |
| Send email | **Mock only** | Same mock as Gmail |
| Calendar sync | **Built** | After OAuth: Graph API calendarView |

**Without credentials:** Not testable.

### 8.3 WhatsApp

| What | Status | How to Test |
|------|--------|-------------|
| Send message | **Built (Twilio)** | Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` |
| Radar alerts | **Built** | Triggered by scout scan tasks |
| Verification | **Built** | Phone number verification flow |

**Without Twilio:** Not testable. API calls will fail with auth errors.

**With Twilio sandbox:**
```bash
# Verify WhatsApp number
curl -s -X POST http://localhost:8000/api/v1/whatsapp/verify \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+447123456789"}' \
  | python3 -m json.tool
```

### 8.4 LinkedIn Messaging

| What | Status | How to Test |
|------|--------|-------------|
| Message capture (extension) | **Built** | Load extension, browse LinkedIn messages |
| Message sync (backend) | **Built** | Extension sends captured messages to backend |
| Send message | **Mock only** | `ActionExecutor._send_linkedin_message()` returns `mock: true` |
| Relationship analysis | **Built** | `POST /api/v1/linkedin/relationships` |

**No public API for LinkedIn messaging.** Send will always be mock until extension UI automation is implemented.

### 8.5 What Is Mock vs Real

| Channel | Read/Capture | Send/Execute |
|---------|-------------|-------------|
| Gmail | **Real** (needs OAuth) | **Mock** |
| Outlook | **Real** (needs OAuth) | **Mock** |
| WhatsApp | N/A | **Real** (needs Twilio) |
| LinkedIn | **Real** (extension) | **Mock** |

**"Mock" means:** The endpoint returns `200` with `mock: true`. No real message is sent. The action status transitions normally. You can test the full lifecycle without any external service.

### FLOW 8 — Checklist

- [ ] Gmail OAuth vars set? → test connect flow / skip
- [ ] Outlook OAuth vars set? → test connect flow / skip
- [ ] Twilio vars set? → test WhatsApp send / skip
- [ ] Extension loaded → LinkedIn capture works
- [ ] Action execute on any channel → returns `mock: true`
- [ ] Action lifecycle works end-to-end regardless of mock

---

## QUICK REFERENCE — What Works Without Any Credentials

Everything below is testable right now with just `make up`:

1. **Auth** — register, login, refresh, logout (Flow 1) ✅
2. **Quick-start** — all input combinations (Flow 3) ✅
3. **Extension capture** — via curl (Flow 4.4–4.6) ✅ *
4. **Signal → Action pipeline** — generate, list, transition, execute mock (Flow 5) ✅
5. **Insights** — if on paid plan (Flow 6) ✅
6. **Plan gating** — quota enforcement, feature gates (Flow 7) ✅
7. **Health check** — /health, /health/ready ✅

\* Extension capture requires Starter+ plan. Use `make psql` to set plan tier.

## What Is Blocked

| Feature | Blocked By | Env Vars Needed |
|---------|-----------|-----------------|
| Google Login | No Google OAuth app | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| Gmail read | No Google OAuth app | Same as above |
| Outlook read | No Azure AD app | Outlook OAuth vars |
| WhatsApp send | No Twilio account | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` |
| Facebook Login | Not implemented | N/A — needs building |
| Email send (real) | Mock only | Needs service wiring |
| LinkedIn send (real) | Mock only | No public API |

---

## TESTING ORDER

Follow this exact sequence:

```
1.  make up                          → stack running
2.  curl /health                     → healthy
3.  FLOW 1 (auth)                    → register, login, refresh, logout
4.  FLOW 3 (quick-start)            → all 4 input types
5.  FLOW 4 (extension capture)       → profile, job, company via curl
6.  FLOW 5 (signal → action)        → generate, list, transition, execute
7.  FLOW 3 again (quick-start)      → now with signals, verify ranking
8.  FLOW 6 (insights)               → verify data populated
9.  FLOW 7 (plan gating)            → test FREE limits, upgrade, re-test
10. FLOW 2 (Google login)           → only if credentials available
11. FLOW 8 (messaging)             → confirm mock status, test if creds available
```

**When something fails:** Stop. Note the exact error. Do not try to fix it during testing. Complete all flows first, collect all failures, then fix in priority order.
