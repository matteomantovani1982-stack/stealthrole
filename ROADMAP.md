# StealthRole — Product Roadmap v3

**Vision**: AI Job Hunter + Opportunity Intelligence Engine
**Date**: 2026-03-18
**Sprint**: 2 weeks (60h budget)

The system proactively detects career opportunities, generates strategy and outreach, and contacts the user when something important appears. Users should not need to search manually. The system works in the background.

---

## Product Pillars

| # | Pillar | What it does | Why it matters |
|---|--------|-------------|----------------|
| 1 | Hidden Market Intelligence | Detects hiring signals before jobs are posted | No competitor does this. Funding rounds, leadership changes, expansions → inferred roles. |
| 2 | OpportunityRadar | Unified ranking engine across all signal sources | One ranked list. Feeds dashboard, WhatsApp, email. Users ask "what should I do today?" |
| 3 | Shadow Applications | Approach companies BEFORE jobs exist | Generates tailored CV + strategy memo + outreach + hiring hypothesis from a signal. |
| 4 | WhatsApp Engagement Layer | Pushes alerts, accepts commands, drives referrals | App reaches users. They don't need to open it. |
| 5 | Email Intelligence Engine | Reconstructs career history from Gmail/Outlook | 5 years of email → structured intel → better scoring, outreach, and profile. |
| 6 | LinkedIn Import | Extract profile data from LinkedIn URL | Enriches candidate profile with experience, skills, companies. |
| 7 | File Ingestion | Parse CVs, JDs, career documents + detect anomalies | Structured extraction + fraud/inconsistency detection. |
| 8 | Automated QA (OpenClaw) | Claude defines tests, OpenClaw runs, Claude fixes | Ship faster. Catch regressions. Minimize manual testing. |

---

## MVP vs Later Phases

### MVP (This Sprint — 2 Weeks)

| Feature | Pillar | Scope |
|---------|--------|-------|
| OpenClaw test loop | QA | e2e coverage of auth, CV, jobs, scout, profile, billing, radar, shadow, outreach, WhatsApp |
| Hidden Market detector | Hidden Market | Adzuna employer surge + Claude Haiku news classification → signals |
| OpportunityRadar | Radar | Unified ranking: hidden market + scout + signal engine. `GET /api/v1/opportunities/radar` |
| Shadow Applications | Shadow | Generate hiring hypothesis + tailored CV + strategy memo + outreach from signal. `POST /api/v1/shadow/generate` |
| Outreach message generator | Outreach | LinkedIn note + cold email + follow-up. `POST /api/v1/outreach/generate` |
| Job Scout real APIs | Scout | Adzuna + JSearch live data, dedup, save jobs |
| WhatsApp alerts + commands | WhatsApp | Twilio sandbox. SCOUT, PACK, STOP, MODE commands. Alert modes. |
| Credit-gated messaging | WhatsApp | Free: 2 alerts/week. Credits: unlimited. Credits consumed on actions only. |
| Viral referral mechanism | Growth | Referral codes in WhatsApp alerts. Both users get credits. |
| Email notifications | Engagement | Pack complete + scout digest + hidden market alerts |
| Profile strength score | Engagement | Heuristic scorer + circular ring UI |
| LinkedIn URL import | LinkedIn | Paste URL → extract experience/skills/companies → enrich profile |
| File ingestion + anomaly detection | Ingestion | CV/JD upload with metadata checks + inconsistency flags |
| Dashboard hub | Dashboard | Single daily view powered by OpportunityRadar |

### Phase 2 (Weeks 3-4)

| Feature | Pillar | Scope |
|---------|--------|-------|
| Email Intelligence MVP | Email Intel | Gmail OAuth + 5-year scan + signal extraction |
| Career History Timeline | Email Intel | Visual timeline reconstructed from email |
| Professional Identity Graph | Email Intel | Companies, contacts, industries mapped |
| Behavior Insights | Email Intel | "You get more interviews in fintech than consulting" |
| WhatsApp production number | WhatsApp | Twilio production approval + dedicated number |
| Hidden Market deep sources | Hidden Market | TechCrunch API, LinkedIn company updates, regional startup media |
| Shadow Application tracking | Shadow | Track shadow apps through to response/interview |

### Phase 3 (Weeks 5-8)

| Feature | Pillar | Scope |
|---------|--------|-------|
| Outlook integration | Email Intel | Microsoft Graph API |
| LinkedIn OAuth | LinkedIn | Full API access, mutual connections, company updates |
| Auto-apply (ATS integration) | Execution | Common ATS form submission |
| Relationship engine | Network | Contact graph from email + LinkedIn |
| Mobile app (PWA) | Reach | Push notifications, offline access |
| Arabic/RTL support | Localization | GCC market expansion |
| Advanced billing tiers | Monetization | Credit bundles, team plans |

---

## Feature Prioritization Matrix

| Feature | Impact | Effort | Differentiation | Daily Use | Priority |
|---------|--------|--------|-----------------|-----------|----------|
| Hidden Market Intelligence | 10 | 6h | Unique | High | P0 |
| OpportunityRadar | 10 | 6h | Unique | Very High | P0 |
| Shadow Applications | 10 | 6h | Unique | High | P0 |
| WhatsApp Alerts + Commands | 9 | 7h | Unique | Very High | P0 |
| OpenClaw Test Loop | 7 | 4h | — | — | P0 (enabler) |
| Outreach Generator | 8 | 5h | High | Medium | P1 |
| Job Scout Real APIs | 7 | 5h | Medium | High | P1 |
| LinkedIn URL Import | 7 | 3h | Medium | Medium | P1 |
| File Ingestion + Anomaly Detection | 6 | 3h | Medium | Low | P1 |
| Email Notifications | 7 | 3h | Low | High | P1 |
| Profile Strength Score | 6 | 3h | Medium | Medium | P1 |
| Viral Referral | 8 | 2h | High | Medium | P1 |
| Dashboard Hub | 6 | 3h | Low | High | P2 |
| Email Intelligence Engine | 10 | 20h+ | Unique | Very High | Phase 2 |

---

## 2-Week Sprint Schedule

### Day 0: OpenClaw Testing Loop (4h)

**Goal**: Green baseline before feature work begins.

| Item | Details |
|------|---------|
| Setup | OpenClaw CLI + `tests/e2e/` structure + Docker stack config |
| Test suites | `test_auth.py`, `test_jobs.py`, `test_scout.py`, `test_profile.py`, `test_billing.py` |
| Loop | Claude defines → OpenClaw runs → Claude fixes → repeat until green |
| Output | Stable baseline; every subsequent feature adds its own test file |

```
tests/e2e/
├── conftest.py
├── test_auth.py
├── test_jobs.py
├── test_scout.py
├── test_profile.py
├── test_billing.py
└── test_full_flow.py
```

---

### Day 1: Hidden Market MVP (6h)

**Goal**: Detect companies likely hiring before jobs are posted.

**Signal types:**
- Funding rounds (Series A/B/C, IPO prep)
- Leadership changes (new CTO, VP Engineering, departures)
- Market expansion (new office, new region, new license)
- Product launches (new product = new team)
- Hiring surge (spike in postings from same employer)
- New office openings

**Backend:**
- `app/services/scout/hidden_market.py` — signal detection engine
  - Source 1: Adzuna employer posting frequency (surge detection)
  - Source 2: Claude Haiku classifies news snippets → `{signal_type, confidence, likely_roles[], reasoning}`
- `app/models/hidden_signal.py` — `HiddenSignal` table
- `GET /api/v1/scout/hidden-market` — ranked signals for user preferences
- Signals include: company, signal_type, confidence, likely_roles[], reasoning, source_url

**Frontend:**
- "Hidden Market" section in Dashboard — signal cards with action buttons
- Each card: company + signal badge + confidence + likely roles
- Buttons: "Generate Shadow App" + "Generate Outreach"

**Migration:** `012_hidden_signals.py`

**Tests:** `tests/e2e/test_hidden_market.py`

---

### Days 2-3: OpportunityRadar + Shadow Applications (8h)

#### OpportunityRadar (4h)

**Goal**: Single ranked list from all sources. Everything else consumes this.

**Backend:**
- `app/services/radar/opportunity_radar.py` — orchestrator: collect → normalize → dedup → score → rank
- `app/services/radar/adapters.py` — source adapters (Hidden Market, Scout Jobs, Signal Engine). Email + LinkedIn stubs return `[]`.
- `app/services/radar/scorer.py` — composite: `profile_fit(35%) + signal_strength(25%) + recency(20%) + competition(10%) + conviction(10%)`
- `app/services/radar/dedup.py` — normalize company/role, group, merge multi-source evidence
- `app/services/radar/types.py` — RadarInput, RadarOpportunity, ScoreBreakdown dataclasses
- `app/api/routes/opportunities.py` — `GET /api/v1/opportunities/radar`
  - Filters: limit, min_score, source, urgency, saved_only, deep
  - `deep=true`: Claude Haiku re-ranks top 20 with reasoning (costs 1 credit)
- Redis cache: 15min TTL

**Output per opportunity:**
- company, role, location, sector
- radar_score (0-100) + score_breakdown
- sources[] (evidence from each source)
- reasoning (human-readable)
- suggested_action
- urgency (high/medium/low)
- actions: can_generate_pack, can_generate_shadow, can_generate_outreach

**Full design doc:** `docs/OPPORTUNITY_RADAR.md`

**Tests:** `tests/e2e/test_radar.py`

#### Shadow Applications (4h)

**Goal**: Approach companies BEFORE jobs exist. The killer differentiator.

When Radar detects a hidden market opportunity, the user can generate a Shadow Application Pack:

**`POST /api/v1/shadow/generate`**

Input:
```json
{
    "company": "TechCo",
    "signal_type": "funding",
    "likely_roles": ["VP Engineering", "Head of Product"],
    "signal_context": "Series C, $50M raised, expanding to MENA",
    "user_profile_id": "uuid",
    "tone": "confident"
}
```

Output:
```json
{
    "shadow_pack": {
        "hypothesis_role": "VP Engineering",
        "hiring_hypothesis": "TechCo just raised $50M Series C and is expanding to MENA. They'll need a VP Engineering to build the regional tech team. Their current engineering leadership is US-based — they need someone who understands MENA talent markets and can build from scratch.",
        "tailored_cv_s3_key": "shadow/uuid/cv.docx",
        "strategy_memo": "Position yourself as the MENA engineering leader they don't know they need yet. Lead with your track record of building engineering teams in the region...",
        "outreach_message": {
            "linkedin_note": "...",
            "cold_email": "...",
            "follow_up": "..."
        },
        "confidence": 0.82,
        "reasoning": "Strong match: your MENA engineering leadership experience + their expansion signal"
    }
}
```

**Pipeline:**
1. Load user's CandidateProfile + active CV
2. Claude Haiku generates hiring hypothesis (why this company needs this role)
3. Claude Sonnet generates tailored CV edits (reuses existing edit_plan pipeline)
4. Claude Haiku generates strategy memo (2 paragraphs: positioning + approach)
5. Claude Haiku generates outreach messages (LinkedIn + email + follow-up)
6. Render tailored CV DOCX, upload to S3
7. Return complete shadow pack

**Backend:**
- `app/api/routes/shadow.py` — POST endpoint
- `app/services/shadow/shadow_service.py` — orchestrator
- `app/services/llm/prompts.py` — add hypothesis + strategy memo prompts
- Costs 1 credit per generation

**Frontend:**
- "Generate Shadow Application" button on Radar cards + Hidden Market cards
- Shadow pack view: hypothesis + strategy memo + CV download + outreach with Copy buttons
- Shadow apps listed in Applications page with "shadow" badge

**Model:** `ShadowApplication` table (or store as special-type JobRun with `source=shadow`)

**Migration:** `013_shadow_applications.py`

**Tests:** `tests/e2e/test_shadow.py`

---

### Days 3-4: Outreach Generator + Email Notifications (6h)

#### Outreach Generator (3h)

- `POST /api/v1/outreach/generate` — Claude Haiku generates:
  - LinkedIn connection note (300 char)
  - Cold email (3 paragraphs)
  - Follow-up message (1 week later)
- Uses candidate profile + target company/role + tone selector
- `/outreach` page: form + generated message cards + Copy buttons
- "Generate Outreach" button on Radar cards, Hidden Market cards, Scout cards

**Files:** `app/api/routes/outreach.py`, `src/pages/Outreach.tsx`, `src/api/outreach.ts`, `Sidebar.tsx`, `App.tsx`

**Tests:** `tests/e2e/test_outreach.py`

#### Email Notifications (3h)

- `send_pack_complete_email()` — triggered on job_run COMPLETED
- `send_scout_digest_email()` — triggered on high-fit scout results
- `send_hidden_market_alert()` — triggered on high-confidence signals
- `send_shadow_ready_email()` — triggered on shadow pack completion
- `notification_preferences` JSONB on User model
- Notification toggles in `Settings.tsx`

**Migration:** `014_notification_preferences.py`

**Tests:** `tests/e2e/test_notifications.py`

---

### Days 4-5: WhatsApp Engagement Layer (7h)

**Twilio Setup (1h):**
- Twilio sandbox account + webhook URL
- Config: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`

**User Model Extensions:**
```
whatsapp_number             String(20)    — E.164 format
whatsapp_verified           Boolean       — confirmed via code
whatsapp_alert_mode         String(20)    — ACTIVE_SEARCH | CASUAL_SEARCH | OFF
whatsapp_weekly_quota_used  Integer       — reset weekly by Celery Beat
whatsapp_weekly_quota_limit Integer       — 2 for free, unlimited for paid
```

**Alert Modes:**

| Mode | Behavior |
|------|----------|
| ACTIVE_SEARCH | Real-time: hidden market signals, high-fit radar opportunities, pack/shadow completion |
| CASUAL_SEARCH | Weekly digest only |
| OFF | No WhatsApp messages |

**Credit-Gated Logic:**
- Notifications are free (telling user something happened)
- Credits consumed only for *actions*:
  - Generate Intelligence Pack (1 credit)
  - Generate Shadow Application (1 credit)
  - Generate Outreach Messages (1 credit)
  - CV Tailoring (1 credit)
  - Hidden Market Deep Analysis (1 credit)
- Free users: max 2 WhatsApp alerts/week, summary only
- Paid users: unlimited alerts, real-time, with direct action links

**WhatsApp Service (`app/services/whatsapp/service.py`):**
- `send_radar_alert(phone, opportunities[])` — top opportunities from Radar
- `send_pack_ready(phone, job_run)` — pack completion + download link
- `send_shadow_ready(phone, shadow)` — shadow app ready + view link
- `send_hidden_market_alert(phone, signals[])` — signal summary + action links
- `send_weekly_digest(phone, summary)` — for CASUAL_SEARCH mode

**Webhook Handler (`POST /api/v1/whatsapp/webhook`):**

| Command | Response |
|---------|----------|
| `SCOUT` | Top 3 from OpportunityRadar |
| `PACK <job_url>` | Triggers intelligence pack, sends link when ready |
| `MODE ACTIVE` | Switches to ACTIVE_SEARCH |
| `MODE CASUAL` | Switches to CASUAL_SEARCH |
| `STOP` | Sets alert_mode to OFF |

**Frontend:**
- WhatsApp section in `Settings.tsx`: phone input, verify, mode selector
- WhatsApp status indicator on Dashboard

**Viral Referral (built into WhatsApp alerts):**
- Every alert includes: *"Know someone job hunting? stealthrole.com/ref/{code}"*
- `referral_code`, `referred_by`, `referral_credits_granted` on User model
- Both referrer and referee receive credits on signup

**Migration:** `015_whatsapp_referral_fields.py` (WhatsApp + referral fields on users)

**Tests:** `tests/e2e/test_whatsapp.py`, `tests/e2e/test_referral.py`

---

### Days 5-6: Job Scout Real APIs + LinkedIn Import (6h)

#### Job Scout Real APIs (4h)

- Activate Adzuna (free, 200/day) + JSearch (freemium, 100/day)
- Dedup: normalize by title + company + location
- Ranking: keyword match to user preferences
- Feed employer posting frequency into Hidden Market detector
- `saved_jobs` table + `POST /api/v1/scout/jobs/{id}/save`
- Real job cards: source badge, salary, "Save" + "Generate Pack" + "Shadow App" buttons

**Config:** `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JSEARCH_API_KEY`

**Migration:** `016_saved_jobs.py`

**Tests:** `tests/e2e/test_scout_real.py`

#### LinkedIn URL Import (2h)

**Goal**: User pastes LinkedIn URL → system extracts structured profile data.

- `POST /api/v1/profile/import-linkedin` — accepts `{"linkedin_url": "https://linkedin.com/in/username"}`
- Backend fetches public profile page (httpx + parsing, no OAuth needed for public profiles)
- Extracts: name, headline, experience (company, title, dates), skills, education
- Returns structured data for user to review + merge into CandidateProfile
- No OAuth required in MVP — just public profile parsing
- Falls back gracefully if LinkedIn blocks (returns partial data or error)

**Files:** `app/services/profile/linkedin_import.py`, `app/api/routes/profiles.py` (extend)

**Tests:** `tests/e2e/test_linkedin_import.py`

---

### Days 6-7: File Ingestion + Profile Strength + Analytics (6h)

#### File Ingestion + Anomaly Detection (3h)

**Goal**: Accept CV, JD, and career document uploads with structured extraction and fraud flags.

Extends existing CV upload pipeline:

- `POST /api/v1/uploads/ingest` — accepts PDF/DOCX, detects document type (CV vs JD vs other)
- Extraction: structured fields (name, dates, companies, roles, skills) via existing parser + Claude Haiku classification
- Anomaly detection checks:
  - Metadata inconsistencies (creation date vs claimed dates)
  - Impossible timelines (overlapping full-time roles)
  - Suspicious formatting (hidden text, white-on-white)
  - Title inflation signals (entry-level dates with senior titles)
- Returns: `{document_type, extracted_data, anomaly_flags[], confidence}`
- Anomaly flags are advisory — shown to user, not blocking

**Files:**
- `app/services/ingest/anomaly_detector.py` (new) — heuristic checks on parsed content
- `app/api/routes/uploads.py` (extend) — add `/ingest` endpoint + anomaly response
- `app/services/llm/prompts.py` — add document classification prompt

**Tests:** `tests/e2e/test_ingestion.py`

#### Profile Strength Score (2h)

- `app/services/profile/strength_scorer.py` — pure heuristic:
  - Headline: 10 pts
  - Global context: 10 pts
  - Experiences (count + completeness): 50 pts
  - Preferences (roles, regions, sectors): 15 pts
  - CV uploaded: 15 pts
- `GET /api/v1/profile/strength` → `{score, max, breakdown[], next_action}`
- `ProfileStrength.tsx` — circular ring + "next action" CTA
- Show on Dashboard + Profile page

**Tests:** `tests/e2e/test_profile_strength.py`

#### Simplified Analytics (1h)

- `GET /api/v1/analytics/summary` — single endpoint
  - `total_applications`, `by_stage` counts, `response_rate`, `avg_keyword_score`
- `AnalyticsBanner.tsx` — 4-number stats strip above kanban
- No charts

**Tests:** `tests/e2e/test_analytics.py`

---

### Days 8-9: Dashboard Hub + Lightweight Timeline (5h)

#### Dashboard Hub (3h)

Redesign `Home.tsx` as the single daily command center, powered by OpportunityRadar:

- Profile strength ring
- Top 5 radar opportunities (from `GET /api/v1/opportunities/radar?limit=5`)
- Hidden market signal count badge
- Recent applications (top 3 with status) + recent shadow apps
- Quick action buttons: New Application, View Scout, Generate Outreach, Generate Shadow App
- WhatsApp connection status
- Credit balance / usage meter

**New route:** `app/api/routes/dashboard.py` — `GET /api/v1/dashboard/summary` aggregates all data

#### Lightweight Timeline (2h)

- `ApplicationEvent` model: `(job_run_id, event_type, title, created_at)`
- Auto-create on: stage change, pack completion, shadow generation, outreach generated
- `GET /api/v1/jobs/{id}/timeline` — simple event list
- Display as `<ul>` with timestamps in IntelPack page
- No reminders, no due dates

**Migration:** `017_application_events.py`

**Tests:** `tests/e2e/test_dashboard.py`, `tests/e2e/test_timeline.py`

---

### Day 10: OpenClaw Full E2E + Polish (5h)

**E2E flow (3h):**
```
register → upload CV → import LinkedIn → fill profile → run scout
→ view hidden market signals → view radar → generate shadow application
→ generate intelligence pack → generate outreach → link WhatsApp
→ receive alert → change kanban stage → view timeline → check dashboard
```
OpenClaw runs full flow. Claude fixes all failures.

**Polish (2h):**
- CSS consistency across new pages
- Loading states for async operations
- Error handling for API failures
- TypeScript types for all new endpoints

---

## Architecture Overview

### System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER TOUCHPOINTS                           │
│                                                                   │
│  Browser (React SPA)           WhatsApp (Twilio)     Email        │
│  ┌───────────────────┐         ┌───────────────┐    ┌─────────┐  │
│  │ Dashboard Hub     │         │ Radar Alerts  │    │ Digest  │  │
│  │ OpportunityRadar  │         │ Shadow Ready  │    │ Alerts  │  │
│  │ Shadow Apps       │         │ Pack Ready    │    │ Shadow  │  │
│  │ Hidden Market     │         │ Hidden Mkt    │    │ Ready   │  │
│  │ Job Scout         │         │ Commands      │    │         │  │
│  │ Intel Packs       │         │ Referral      │    │         │  │
│  │ Outreach Gen      │         └──────┬────────┘    └────┬────┘  │
│  │ Applications      │                │                  │        │
│  │ Profile           │                │                  │        │
│  └────────┬──────────┘                │                  │        │
└───────────┼───────────────────────────┼──────────────────┼────────┘
            │                           │                  │
            ▼                           ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                       FastAPI (API Layer)                          │
│                                                                   │
│  /auth       /jobs       /scout        /outreach      /whatsapp   │
│  /cvs        /billing    /analytics    /dashboard     /referral   │
│  /opportunities/radar    /shadow       /profile       /uploads    │
│                                                                   │
│  Dependencies: CurrentUser, DB, S3Client, QuotaGuard, CreditGuard │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌───────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│  Services         │ │ Celery       │ │  External APIs       │
│                   │ │ Workers      │ │                      │
│ OpportunityRadar  │ │ parse_cv     │ │ Anthropic Claude     │
│ ShadowService     │ │ run_llm      │ │ Adzuna (200/day)     │
│ HiddenMarket      │ │ render_docx  │ │ JSearch (100/day)    │
│ SignalEngine      │ │ scout_scan   │ │ Twilio WhatsApp      │
│ AnomalyDetector   │ │ shadow_gen   │ │ SMTP                 │
│ LinkedInImporter  │ │ weekly_digest│ │ S3/MinIO             │
│ StrengthScorer    │ │ quota_reset  │ │                      │
│ WhatsAppService   │ └──────────────┘ └──────────────────────┘
│ EmailService      │
│ OutreachGen       │
│ ProfileService    │
│ BillingService    │
└───────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Data Layer                                   │
│                                                                   │
│  PostgreSQL 16              Redis 7            MinIO (S3)          │
│  ┌─────────────────────┐    ┌──────────────┐   ┌──────────────┐  │
│  │ users               │    │ Celery broker│   │ CVs (DOCX)   │  │
│  │ cvs                 │    │ Task results │   │ Output DOCX  │  │
│  │ candidate_profiles  │    │ Radar cache  │   │ Shadow CVs   │  │
│  │ experience_entries  │    │ Scout cache  │   │              │  │
│  │ job_runs            │    │ Rate limits  │   │              │  │
│  │ job_steps           │    └──────────────┘   └──────────────┘  │
│  │ scout_results       │                                          │
│  │ hidden_signals      │  ← NEW                                   │
│  │ shadow_applications │  ← NEW                                   │
│  │ saved_jobs          │  ← NEW                                   │
│  │ application_events  │  ← NEW                                   │
│  │ subscriptions       │                                          │
│  │ cv_templates        │                                          │
│  └─────────────────────┘                                          │
└──────────────────────────────────────────────────────────────────┘
```

### Core Data Flow: Signal → Radar → Shadow → Outreach

```
Signal detected (Hidden Market / Scout / Email Intel)
    │
    ▼
OpportunityRadar
    │ normalize → dedup → score → rank
    │
    ▼
Ranked opportunity list
    │
    ├─► Dashboard (top 5)
    ├─► WhatsApp alert (top 3, score >= 70)
    ├─► Email digest (top 10)
    │
    └─► User clicks "Generate Shadow Application"
            │
            ▼
        ShadowService
            │ 1. Generate hiring hypothesis (Claude Haiku)
            │ 2. Tailor CV (Claude Sonnet + render_docx)
            │ 3. Generate strategy memo (Claude Haiku)
            │ 4. Generate outreach (Claude Haiku)
            │
            ▼
        Shadow Application Pack
            │
            ├─► View in app (hypothesis + CV download + memo + outreach)
            ├─► WhatsApp: "Shadow app ready for VP Eng @ TechCo"
            └─► Email: shadow pack summary with links
```

### Notification Flow

```
Event occurs (radar match / pack complete / shadow ready / hidden signal)
    │
    ▼
Check user.notification_preferences
    │
    ├─ email enabled? ──► EmailService.send_*()
    │
    └─ whatsapp enabled?
        │
        ├─ alert_mode == OFF? ──► skip
        │
        ├─ alert_mode == CASUAL? ──► queue for weekly digest
        │
        └─ alert_mode == ACTIVE?
            │
            ├─ has credits? ──► real-time alert with action links
            │
            └─ free user?
                │
                ├─ weekly_quota_used < 2? ──► summary alert (no action links)
                │
                └─ quota exceeded ──► skip, include in weekly digest
```

### WhatsApp Command Flow

```
Incoming message (Twilio webhook)
    │
    ▼
POST /api/v1/whatsapp/webhook
    │
    ├─ SCOUT   ──► OpportunityRadar top 3 ──► format ──► reply
    │
    ├─ PACK <url> ──► check credits ──► create job_run ──► "generating..."
    │                                                        └─► send link when ready
    │
    ├─ MODE ACTIVE ──► update alert_mode ──► confirm
    ├─ MODE CASUAL ──► update alert_mode ──► confirm
    │
    ├─ STOP ──► set OFF ──► confirm
    │
    └─ Unknown ──► reply with command list
```

---

## API Endpoints Overview

### Existing (unchanged)
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
POST   /api/v1/cvs
GET    /api/v1/cvs
GET    /api/v1/cvs/{id}
POST   /api/v1/jobs
GET    /api/v1/jobs
GET    /api/v1/jobs/{id}
GET    /api/v1/jobs/{id}/download
POST   /api/v1/jobs/extract-jd
GET    /api/v1/profiles
POST   /api/v1/profiles
PUT    /api/v1/profiles/{id}
POST   /api/v1/billing/subscribe
GET    /api/v1/billing/plans
```

### New — OpportunityRadar
```
GET    /api/v1/opportunities/radar      → unified ranked opportunity list
                                          filters: limit, min_score, source, urgency, saved_only, deep
```

### New — Shadow Applications
```
POST   /api/v1/shadow/generate          → generate shadow application pack
                                          input: company, signal_type, likely_roles, user_profile
                                          output: hypothesis_role, tailored_cv, strategy_memo, outreach
GET    /api/v1/shadow                   → list user's shadow applications
GET    /api/v1/shadow/{id}              → get shadow application detail
```

### New — Hidden Market
```
GET    /api/v1/scout/hidden-market      → ranked hidden signals for user
```

### New — Outreach
```
POST   /api/v1/outreach/generate        → generate LinkedIn/email/follow-up messages
```

### New — WhatsApp
```
POST   /api/v1/whatsapp/webhook         → Twilio incoming message handler
POST   /api/v1/whatsapp/verify          → send verification code
POST   /api/v1/whatsapp/confirm         → confirm code, activate WhatsApp
```

### New — File Ingestion
```
POST   /api/v1/uploads/ingest           → upload + parse + anomaly detection
                                          returns: document_type, extracted_data, anomaly_flags[]
```

### New — LinkedIn Import
```
POST   /api/v1/profile/import-linkedin  → extract profile from LinkedIn URL
                                          input: linkedin_url
                                          output: name, headline, experiences[], skills[]
```

### New — Analytics
```
GET    /api/v1/analytics/summary        → total apps, by_stage, response_rate, avg_score
```

### New — Profile Strength
```
GET    /api/v1/profile/strength         → score, breakdown, next_action
```

### New — Dashboard
```
GET    /api/v1/dashboard/summary        → aggregated daily view data
```

### New — Timeline
```
GET    /api/v1/jobs/{id}/timeline       → list of application events
```

### New — Referral
```
GET    /api/v1/referral/stats           → referral count + credits earned
```

### New — Saved Jobs
```
POST   /api/v1/scout/jobs/{id}/save     → save job
GET    /api/v1/scout/jobs/saved         → list saved
DELETE /api/v1/scout/jobs/{id}/save     → unsave
```

### Modified — Scout (real APIs)
```
GET    /api/v1/scout/signals            → now includes signal_source field
GET    /api/v1/scout/jobs               → Adzuna + JSearch (not mocked)
```

### Modified — Auth
```
POST   /api/v1/auth/register            → accepts optional ?ref= for referral
```

### Modified — Settings
```
PUT    /api/v1/auth/me/notifications    → update notification_preferences
PUT    /api/v1/auth/me/whatsapp         → update WhatsApp settings
```

---

## Database Schema Changes

### Migration 012: `hidden_signals`
```sql
CREATE TABLE hidden_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    company_name    VARCHAR(255) NOT NULL,
    signal_type     VARCHAR(50) NOT NULL,
    confidence      FLOAT NOT NULL,
    likely_roles    JSONB NOT NULL DEFAULT '[]',
    reasoning       TEXT,
    source_url      VARCHAR(2000),
    source_name     VARCHAR(100),
    is_dismissed    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_hidden_signals_user_id ON hidden_signals(user_id);
CREATE INDEX ix_hidden_signals_created_at ON hidden_signals(created_at DESC);
```

### Migration 013: `shadow_applications`
```sql
CREATE TABLE shadow_applications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    profile_id          UUID REFERENCES candidate_profiles(id),
    cv_id               UUID REFERENCES cvs(id),

    -- Signal context
    company             VARCHAR(255) NOT NULL,
    signal_type         VARCHAR(50) NOT NULL,
    signal_context      TEXT,
    hidden_signal_id    UUID REFERENCES hidden_signals(id),
    radar_opportunity_id VARCHAR(255),

    -- Generated outputs
    hypothesis_role     VARCHAR(255),
    hiring_hypothesis   TEXT,
    strategy_memo       TEXT,
    outreach_linkedin   TEXT,
    outreach_email      TEXT,
    outreach_followup   TEXT,

    -- Tailored CV
    tailored_cv_s3_key  VARCHAR(1000),
    tailored_cv_s3_bucket VARCHAR(255),

    -- Scoring
    confidence          FLOAT,
    reasoning           TEXT,

    -- Status
    status              VARCHAR(20) NOT NULL DEFAULT 'generating',
    error_message       TEXT,
    celery_task_id      VARCHAR(255),

    -- Tracking
    pipeline_stage      VARCHAR(20) DEFAULT 'created',
    pipeline_notes      TEXT,

    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_shadow_applications_user_id ON shadow_applications(user_id);
CREATE INDEX ix_shadow_applications_company ON shadow_applications(company);
```

### Migration 014: `notification_preferences` on users
```sql
ALTER TABLE users ADD COLUMN notification_preferences JSONB NOT NULL DEFAULT '{
    "pack_complete_email": true,
    "scout_digest_email": true,
    "hidden_market_email": true,
    "shadow_ready_email": true
}';
```

### Migration 015: WhatsApp + referral fields on users
```sql
ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(20);
ALTER TABLE users ADD COLUMN whatsapp_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN whatsapp_alert_mode VARCHAR(20) DEFAULT 'OFF';
ALTER TABLE users ADD COLUMN whatsapp_weekly_quota_used INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN whatsapp_weekly_quota_limit INTEGER DEFAULT 2;
ALTER TABLE users ADD COLUMN referral_code VARCHAR(20) UNIQUE;
ALTER TABLE users ADD COLUMN referred_by UUID REFERENCES users(id);
ALTER TABLE users ADD COLUMN referral_credits_granted INTEGER DEFAULT 0;
CREATE UNIQUE INDEX ix_users_referral_code ON users(referral_code);
```

### Migration 016: `saved_jobs`
```sql
CREATE TABLE saved_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    source      VARCHAR(50) NOT NULL,
    external_id VARCHAR(255),
    title       VARCHAR(500) NOT NULL,
    company     VARCHAR(255),
    location    VARCHAR(255),
    salary_min  INTEGER,
    salary_max  INTEGER,
    url         VARCHAR(2000),
    metadata    JSONB DEFAULT '{}',
    saved_at    TIMESTAMPTZ DEFAULT now(),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_saved_jobs_user_id ON saved_jobs(user_id);
CREATE UNIQUE INDEX ix_saved_jobs_user_source_ext ON saved_jobs(user_id, source, external_id);
```

### Migration 017: `application_events`
```sql
CREATE TABLE application_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_run_id  UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    event_type  VARCHAR(50) NOT NULL,
    title       VARCHAR(255) NOT NULL,
    detail      TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_application_events_job_run_id ON application_events(job_run_id);
```

---

## File Manifest

### New Backend Files
```
# Shadow Applications
app/api/routes/shadow.py                    — shadow generation + list + detail endpoints
app/services/shadow/__init__.py
app/services/shadow/shadow_service.py       — orchestrator: hypothesis → CV → memo → outreach
app/models/shadow_application.py            — ShadowApplication ORM model

# OpportunityRadar
app/api/routes/opportunities.py             — GET /api/v1/opportunities/radar
app/services/radar/__init__.py
app/services/radar/opportunity_radar.py     — orchestrator: collect → normalize → dedup → score → rank
app/services/radar/adapters.py              — source adapters (hidden_market, scout, signal_engine)
app/services/radar/scorer.py                — heuristic + Claude deep scorer
app/services/radar/dedup.py                 — company/role normalization + merge
app/services/radar/types.py                 — RadarInput, RadarOpportunity, ScoreBreakdown

# Hidden Market
app/services/scout/hidden_market.py         — signal detection engine
app/models/hidden_signal.py                 — HiddenSignal ORM model

# WhatsApp
app/services/whatsapp/__init__.py
app/services/whatsapp/service.py            — Twilio WhatsApp dispatch
app/api/routes/whatsapp.py                  — webhook + verify + confirm

# File Ingestion
app/services/ingest/anomaly_detector.py     — document anomaly checks

# LinkedIn Import
app/services/profile/linkedin_import.py     — extract from public LinkedIn URL

# Profile Strength
app/services/profile/strength_scorer.py     — heuristic scoring

# Other
app/api/routes/outreach.py                  — outreach generation
app/api/routes/analytics.py                 — simplified analytics
app/api/routes/dashboard.py                 — dashboard aggregation
app/models/saved_job.py                     — SavedJob ORM model
app/models/application_event.py             — ApplicationEvent ORM model

# Migrations
app/db/migrations/versions/012_hidden_signals.py
app/db/migrations/versions/013_shadow_applications.py
app/db/migrations/versions/014_notification_preferences.py
app/db/migrations/versions/015_whatsapp_referral_fields.py
app/db/migrations/versions/016_saved_jobs.py
app/db/migrations/versions/017_application_events.py

# Tests
tests/e2e/conftest.py
tests/e2e/test_auth.py
tests/e2e/test_jobs.py
tests/e2e/test_scout.py
tests/e2e/test_profile.py
tests/e2e/test_billing.py
tests/e2e/test_hidden_market.py
tests/e2e/test_radar.py
tests/e2e/test_shadow.py
tests/e2e/test_outreach.py
tests/e2e/test_notifications.py
tests/e2e/test_whatsapp.py
tests/e2e/test_referral.py
tests/e2e/test_scout_real.py
tests/e2e/test_linkedin_import.py
tests/e2e/test_ingestion.py
tests/e2e/test_profile_strength.py
tests/e2e/test_analytics.py
tests/e2e/test_dashboard.py
tests/e2e/test_timeline.py
tests/e2e/test_full_flow.py
openclaw.config.yaml
```

### New Frontend Files
```
src/pages/Outreach.tsx                      — outreach generator page
src/pages/ShadowPack.tsx                    — shadow application detail view
src/api/outreach.ts                         — outreach API client
src/api/analytics.ts                        — analytics API client
src/api/shadow.ts                           — shadow application API client
src/api/radar.ts                            — OpportunityRadar API client
src/components/application/AnalyticsBanner.tsx
src/components/dashboard/ProfileStrength.tsx
src/components/dashboard/RadarCard.tsx      — single radar opportunity card
```

### Modified Backend Files
```
app/config.py                               — Twilio + Adzuna + JSearch config
app/models/user.py                          — notification_preferences, whatsapp, referral fields
app/models/scout_result.py                  — signal_source field
app/services/email/service.py               — pack + scout + hidden market + shadow emails
app/services/llm/prompts.py                 — signal classification + outreach + hypothesis + memo prompts
app/workers/tasks/run_llm.py                — hook email + WhatsApp on completion
app/workers/tasks/scout_scan.py             — hook email + WhatsApp on signals, feed hidden market
app/api/routes/scout.py                     — real APIs, hidden market endpoint, save jobs
app/api/routes/jobs.py                      — timeline endpoint
app/api/routes/profiles.py                  — strength score + LinkedIn import endpoints
app/api/routes/uploads.py                   — ingest endpoint with anomaly detection
app/api/routes/auth.py                      — referral code on register
```

### Modified Frontend Files
```
src/pages/Home.tsx                          — dashboard hub redesign
src/pages/Dashboard.tsx                     — radar cards + hidden market + real jobs
src/pages/Applications.tsx                  — analytics banner + shadow app listing
src/pages/IntelPack.tsx                     — timeline list
src/pages/Settings.tsx                      — notification + WhatsApp toggles
src/components/layout/Sidebar.tsx           — add Outreach nav item
src/App.tsx                                 — add /outreach, /shadow/:id routes
src/types/index.ts                          — new interfaces
```

---

## External APIs

| API | Cost | Rate Limit | Purpose |
|-----|------|-----------|---------|
| Anthropic Claude (Haiku) | Existing credits | — | Signal classification, outreach, hypothesis, strategy memo |
| Anthropic Claude (Sonnet) | Existing credits | — | Intelligence packs, positioning, CV tailoring |
| Adzuna | Free | 200/day | Live job data + employer surge for hidden market |
| JSearch (RapidAPI) | Free tier | 100/day | Additional job source |
| Twilio WhatsApp | Free sandbox | — | WhatsApp alerts + commands |
| SMTP | Existing | — | Email notifications |

---

## Time Budget

| Day | Feature | Hours |
|-----|---------|-------|
| 0 | OpenClaw test loop | 4h |
| 1 | Hidden Market MVP | 6h |
| 2-3 | OpportunityRadar + Shadow Applications | 8h |
| 3-4 | Outreach generator + email notifications | 6h |
| 4-5 | WhatsApp engagement + referral | 7h |
| 5-6 | Job Scout real APIs + LinkedIn import | 6h |
| 6-7 | File ingestion + profile strength + analytics | 6h |
| 8-9 | Dashboard hub + lightweight timeline | 5h |
| 10 | OpenClaw full E2E + polish | 5h |
| — | **Buffer** | **7h** |
| — | **Total** | **60h** |

---

## Email Intelligence Engine — Phase 2 Architecture (Preview)

Not in this sprint, but the architecture accommodates it.

**OAuth Integration:**
- Gmail: Google OAuth 2.0 + Gmail API (messages.list, messages.get)
- Outlook: Microsoft Graph API (mail endpoints)

**Processing Pipeline:**
```
OAuth connect → incremental sync (last 5 years)
    → Claude Haiku classification per email thread
    → extract: company, role, stage, contact, industry, location, timeline
    → build: career_history_events table
    → derive: Professional Identity Graph, Behavior Insights
```

**Signals detected:**
- Past job applications
- Recruiter conversations
- Interview invitations
- Rejection emails
- Offers received
- Networking conversations
- Consulting proposals
- Partnership discussions
- CV attachments sent

**What it feeds:**
- OpportunityRadar scoring (prior interaction boost)
- Profile strength scoring (auto-fill experiences)
- Job scout ranking (prefer industries where user has history)
- Hidden market scoring (boost signals for companies user has interacted with)
- Outreach generation (reference prior conversations)
- Intelligence packs (flag "you previously applied here")
- Shadow applications (richer context for hypothesis)

**Privacy:**
- Store structured metadata only, not full email bodies
- User can disconnect at any time
- Incremental sync (not full reprocess)
- Encrypted at rest

**Tables (Phase 2):**
```
email_connections      — OAuth tokens, sync state per provider
career_events          — extracted signals (company, role, stage, date, contact)
identity_graph_edges   — relationships between user and companies/contacts
```

---

## What Users Experience After This Sprint

**Morning (passive):**
WhatsApp: *"TechCo just raised $50M Series C. Likely hiring VP Engineering in Dubai. Radar score: 87. Reply SCOUT for more or tap to generate a Shadow Application."*

**Open app (active):**
Dashboard: strength score (72%), 5 radar opportunities with scores, 3 hidden market signals, recent shadow apps + intel packs, credit balance.

**See hidden signal:**
One tap → Shadow Application: hiring hypothesis + tailored CV + strategy memo + outreach messages. All generated automatically.

**See posted job:**
One tap → Intelligence Pack. Or one tap → Outreach message.

**Pack/Shadow ready:**
WhatsApp + email notification with links.

**Track progress:**
Kanban with auto-logged timeline. Shadow apps and intel packs in one view.

**Share:**
Every alert: *"Know someone job hunting? stealthrole.com/ref/matt42"*

**The system finds opportunities, builds strategy, generates documents, and contacts the user. They just decide and act.**
