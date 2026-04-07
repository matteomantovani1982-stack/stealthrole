# OpportunityRadar Module — Architecture & Design

## Purpose

OpportunityRadar is a **unified ranking layer** that sits above all signal sources. It combines:

1. **Hidden Market** signals (funding, leadership, expansion, hiring surge)
2. **Job Scout** results (Adzuna, JSearch, Serper live postings)
3. **Email Intelligence** signals (prior interactions, recruiter outreach, past applications) — Phase 2
4. **LinkedIn** signals (company updates, mutual connections, profile views) — Phase 3

It outputs a single **ranked opportunity list** with a composite score and per-source reasoning, exposed via `GET /api/v1/opportunities/radar`.

This becomes the primary endpoint the Dashboard, WhatsApp alerts, and email digests consume — replacing the current pattern where each source is queried independently.

---

## Design Principles

1. **One ranked list, not four.** Users don't care where the signal came from. They care: "what should I do today?"
2. **Score = actionability, not just fit.** A 95% fit role posted 3 months ago with 500 applicants scores lower than a 75% fit hidden market signal from yesterday with no competition.
3. **Explain the score.** Every opportunity includes human-readable reasoning: why it ranked here, what the user should do next.
4. **Source-agnostic input, source-aware boosting.** The radar doesn't know about Adzuna vs JSearch internals — it receives normalized opportunities. But it boosts based on source metadata (e.g., hidden market + posted job for same company = high conviction).
5. **Fast path + deep path.** Heuristic scoring for instant response. Optional Claude re-ranking for premium users or digest generation.

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        SIGNAL SOURCES                            │
│                                                                  │
│  Hidden Market       Job Scout         Email Intel    LinkedIn   │
│  (hidden_signals)    (scout_results)   (Phase 2)     (Phase 3)  │
│  ┌──────────────┐    ┌──────────────┐                            │
│  │ funding      │    │ adzuna jobs  │                            │
│  │ leadership   │    │ jsearch jobs │                            │
│  │ expansion    │    │ serper jobs  │                            │
│  │ hiring surge │    │ signal cards │                            │
│  └──────┬───────┘    └──────┬───────┘                            │
└─────────┼───────────────────┼────────────────────────────────────┘
          │                   │
          ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    NORMALIZER                                     │
│                                                                  │
│  Each source adapter converts raw data → RadarOpportunity        │
│  (company, role, location, source, signal_type, metadata)        │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DEDUP + MERGE                                  │
│                                                                  │
│  Group by (company_normalized, role_normalized)                   │
│  Merge signals: funding + posted job for same company            │
│  = single opportunity with multiple evidence sources             │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SCORER                                         │
│                                                                  │
│  Fast path (heuristic):                                          │
│    profile_fit × signal_strength × recency × competition         │
│                                                                  │
│  Deep path (Claude Haiku, optional):                             │
│    re-rank top 20 with reasoning                                 │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    OUTPUT                                         │
│                                                                  │
│  GET /api/v1/opportunities/radar                                 │
│                                                                  │
│  → ranked list of RadarOpportunity with:                         │
│    score, breakdown, reasoning, suggested_action, source_tags    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Data Structure

### RadarOpportunity (output shape)

```python
{
    "id": "uuid",
    "rank": 1,

    # Identity
    "company": "TechCo",
    "company_normalized": "techco",
    "role": "VP Engineering",
    "location": "Dubai, UAE",
    "sector": "fintech",

    # Score
    "radar_score": 87,           # 0-100 composite
    "score_breakdown": {
        "profile_fit": 0.85,     # how well user matches (0-1)
        "signal_strength": 0.90, # quality of evidence (0-1)
        "recency": 0.95,         # how fresh (0-1)
        "competition": 0.70,     # inverse of expected competition (0-1)
        "conviction": 0.80,      # multiple sources agree (0-1)
    },

    # Evidence
    "sources": [
        {
            "type": "hidden_market",
            "signal_type": "funding",
            "headline": "TechCo raises $50M Series C",
            "source_url": "https://techcrunch.com/...",
            "detected_at": "2026-03-17T09:00:00Z",
        },
        {
            "type": "job_board",
            "platform": "linkedin",
            "title": "VP Engineering - Dubai",
            "url": "https://linkedin.com/jobs/...",
            "posted_date": "2026-03-15",
            "salary": "$180K-$220K",
        }
    ],
    "source_tags": ["hidden_market", "linkedin"],   # quick filter

    # Reasoning
    "reasoning": "TechCo just raised Series C ($50M) and is actively hiring VP Engineering in Dubai. Your fintech operations background + MENA experience is a strong match. Low competition — role posted 2 days ago with no LinkedIn Easy Apply (direct applications only).",
    "suggested_action": "Send LinkedIn connection request to CTO with outreach hook referencing their Series C.",
    "outreach_hook": "Saw the Series C announcement — impressive growth. I've scaled engineering orgs through exactly this stage in MENA.",
    "urgency": "high",                # high | medium | low
    "timeline": "immediate",          # immediate | 1-3_months | 3-6_months

    # Actions available
    "actions": {
        "can_generate_pack": true,
        "can_generate_shadow": true,   # shadow application (for hidden market signals)
        "can_generate_outreach": true,
        "can_save": true,
        "pack_job_run_id": null,       # if pack already generated
        "shadow_app_id": null,         # if shadow already generated
    },

    # Metadata
    "first_seen_at": "2026-03-15T00:00:00Z",
    "last_updated_at": "2026-03-17T09:00:00Z",
    "is_saved": false,
    "is_dismissed": false,
}
```

---

## Scoring Algorithm

### Composite Score Formula

```
radar_score = round(
    profile_fit     × 35
  + signal_strength × 25
  + recency         × 20
  + competition     × 10
  + conviction      × 10
)
```

Weights reflect the product philosophy: **fit matters most, but fresh + unique signals are what make this tool worth opening daily.**

### Component Scoring

#### 1. Profile Fit (0-1, weight: 35%)

Heuristic match between opportunity and user's CandidateProfile + preferences:

| Factor | Method | Points |
|--------|--------|--------|
| Role title match | Fuzzy match against `preferences.roles` | 0.30 |
| Seniority match | Level alignment (C-suite, VP, Director, Manager) | 0.20 |
| Sector match | Exact or parent-sector match against `preferences.sectors` | 0.20 |
| Region match | Exact match against `preferences.regions` | 0.15 |
| Company type match | Match against `preferences.companyType` (startup, corporate, PE) | 0.10 |
| Experience overlap | User has experience at similar company or in similar domain | 0.05 |

Deep path: Claude Haiku re-scores top opportunities against full profile context for nuanced fit assessment.

#### 2. Signal Strength (0-1, weight: 25%)

How strong is the evidence that this opportunity is real and actionable?

| Signal combination | Score |
|--------------------|-------|
| Hidden market signal + posted job for same company | 1.0 |
| Posted job with salary + requirements | 0.9 |
| Multiple hidden market signals for same company | 0.85 |
| Single hidden market signal (funding/expansion) | 0.7 |
| Posted job without salary | 0.6 |
| Single hidden market signal (velocity only) | 0.5 |
| Stale/unverified signal | 0.3 |

Phase 2 boost: If Email Intelligence shows prior interaction with this company → +0.15

#### 3. Recency (0-1, weight: 20%)

```python
days_old = (now - most_recent_signal_date).days
recency = max(0.0, 1.0 - days_old / 60.0)   # linear decay over 60 days
```

Signals older than 60 days get recency = 0 (still appear, but penalized).

#### 4. Competition (0-1, weight: 10%)

Inverse of expected applicant volume. Heuristic:

| Indicator | Score |
|-----------|-------|
| Hidden market only (no public posting) | 1.0 |
| Posted < 3 days ago | 0.8 |
| Posted 3-7 days ago | 0.6 |
| Posted 7-14 days ago | 0.4 |
| Posted > 14 days ago OR Easy Apply enabled | 0.2 |
| Unknown | 0.5 |

#### 5. Conviction (0-1, weight: 10%)

How many independent sources confirm this opportunity?

| Sources | Score |
|---------|-------|
| 3+ independent sources | 1.0 |
| 2 independent sources | 0.75 |
| 1 source, high-authority (TechCrunch, Bloomberg, LinkedIn) | 0.6 |
| 1 source, low-authority | 0.4 |

Phase 2: Email Intelligence confirmation (prior interaction) counts as +1 source.

---

## Source Adapters

Each adapter normalizes raw data into `RadarInput` — a flat dict the scorer consumes.

### Adapter 1: Hidden Market → RadarInput

```python
def adapt_hidden_signal(signal: HiddenSignal, user_prefs: dict) -> RadarInput:
    return {
        "company": signal.company_name,
        "role": signal.likely_roles[0] if signal.likely_roles else None,
        "location": None,  # inferred from user prefs or signal source
        "sector": None,    # inferred from signal context
        "source_type": "hidden_market",
        "signal_type": signal.signal_type,
        "headline": f"{signal.company_name}: {signal.signal_type}",
        "detail": signal.reasoning,
        "source_url": signal.source_url,
        "confidence": signal.confidence,
        "detected_at": signal.created_at,
        "salary": None,
        "is_posted": False,
    }
```

### Adapter 2: Job Scout (Adzuna/JSearch/Serper) → RadarInput

```python
def adapt_scout_job(job: dict) -> RadarInput:
    return {
        "company": job["company"],
        "role": job["title"],
        "location": job["location"],
        "sector": None,  # inferred during scoring
        "source_type": "job_board",
        "signal_type": "posted_job",
        "headline": job["title"],
        "detail": job["snippet"],
        "source_url": job["url"],
        "confidence": 1.0,  # it's a real posted job
        "detected_at": job.get("posted_date"),
        "salary": job.get("salary"),
        "is_posted": True,
        "platform": job["source"],  # LinkedIn, Adzuna, Indeed, etc.
    }
```

### Adapter 3: Signal Engine OpportunityCards → RadarInput

```python
def adapt_signal_card(card: dict) -> RadarInput:
    return {
        "company": card["company"],
        "role": card.get("suggested_role") or card.get("posted_title"),
        "location": card.get("location"),
        "sector": card.get("sector"),
        "source_type": "signal_engine",
        "signal_type": card["signals"][0]["signal_type"] if card.get("signals") else "unknown",
        "headline": card.get("signal_summary", ""),
        "detail": "",
        "source_url": card.get("apply_url", ""),
        "confidence": card.get("fit_score", 50) / 100.0,
        "detected_at": None,
        "salary": card.get("salary_estimate"),
        "is_posted": card.get("is_posted", False),
        "fit_score_precomputed": card.get("fit_score"),
        "fit_reasons": card.get("fit_reasons", []),
        "red_flags": card.get("red_flags", []),
        "outreach_hook": card.get("outreach_hook", ""),
    }
```

### Adapter 4: Email Intelligence → RadarInput (Phase 2)

```python
def adapt_email_signal(event: CareerEvent) -> RadarInput:
    return {
        "company": event.company,
        "role": event.role,
        "location": event.location,
        "sector": event.industry,
        "source_type": "email_intelligence",
        "signal_type": event.event_type,  # application | recruiter_outreach | interview | offer
        "headline": f"Prior interaction: {event.event_type} at {event.company}",
        "detail": f"Contact: {event.contact_person}. Last interaction: {event.date}",
        "source_url": None,
        "confidence": 0.9,
        "detected_at": event.date,
        "salary": None,
        "is_posted": False,
        "prior_interaction": True,
        "contact_person": event.contact_person,
    }
```

---

## Dedup + Merge Logic

Opportunities are grouped by normalized key: `(company_lower_stripped, role_normalized)`.

Role normalization:
- "VP Engineering" = "VP of Engineering" = "Vice President Engineering"
- "Senior Software Engineer" = "Sr. Software Engineer"
- Uses a simple alias map, not fuzzy matching (fast, deterministic).

When multiple sources map to the same key:
- Merge `sources[]` array (keep all evidence)
- Take highest `confidence` across sources
- Take most recent `detected_at`
- Merge `salary` (prefer explicit over estimate)
- Set `conviction` score based on source count
- If hidden_market + job_board both present → boost `signal_strength` to 1.0

---

## API Design

### `GET /api/v1/opportunities/radar`

**Auth:** Required (JWT)

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max results (1-50) |
| `offset` | int | 0 | Pagination offset |
| `min_score` | int | 0 | Filter: minimum radar_score |
| `source` | string | all | Filter: `hidden_market`, `job_board`, `signal_engine`, `all` |
| `urgency` | string | all | Filter: `high`, `medium`, `low`, `all` |
| `saved_only` | bool | false | Only return saved opportunities |
| `include_dismissed` | bool | false | Include dismissed opportunities |
| `deep` | bool | false | Use Claude re-ranking (costs 1 credit, slower) |

**Response:**

```json
{
    "opportunities": [
        { /* RadarOpportunity */ }
    ],
    "total": 47,
    "returned": 20,
    "offset": 0,
    "scoring": {
        "method": "heuristic",       // or "claude_reranked"
        "profile_completeness": 0.72,
        "sources_active": ["hidden_market", "adzuna", "jsearch"],
        "sources_unavailable": ["email_intelligence", "linkedin"],
        "last_scan_at": "2026-03-18T06:00:00Z",
    },
    "meta": {
        "cache_hit": false,
        "scored_in_ms": 142,
    }
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| 401 | Invalid/missing JWT |
| 402 | `deep=true` but no credits remaining |
| 429 | Rate limit (max 10 radar calls/minute) |

---

## Caching Strategy

| Layer | TTL | Key | Invalidation |
|-------|-----|-----|-------------|
| Full radar response | 15 min | `radar:{user_id}:{params_hash}` | New scout scan, new hidden signal, user saves/dismisses |
| Hidden market signals | 30 min | `hidden:{user_id}` | New scan completes |
| Scout jobs | 30 min | `scout:{user_id}:{keywords}` | Existing behavior |
| Profile fit scores | Until profile change | `fit:{user_id}:{profile_version}` | Profile updated |

Cache stored in Redis. `deep=true` requests bypass cache and always re-score.

---

## Integration Points

### Dashboard (`Home.tsx`)
```
Dashboard calls GET /api/v1/opportunities/radar?limit=5
Shows top 5 opportunities as cards.
Each card has: score ring, company, role, source badges, "Generate Pack" button.
```

### WhatsApp Alerts
```
When daily_scout_scan completes:
  1. Run OpportunityRadar for user
  2. Filter: radar_score >= 70 AND urgency in (high, medium)
  3. Send top 3 via WhatsApp (if alert_mode == ACTIVE_SEARCH)
  4. Or queue for weekly digest (if CASUAL_SEARCH)
```

### Email Digest
```
Weekly/daily digest email:
  1. Run OpportunityRadar for user
  2. Include top 10 with reasoning
  3. Highlight any new hidden market signals
```

### Outreach Generator
```
When user clicks "Generate Outreach" on a radar opportunity:
  1. Pass full RadarOpportunity (including sources + reasoning) to outreach prompt
  2. Claude uses signal context to craft targeted message
  3. e.g., "Reference their Series C" or "Mention you saw the VP departure"
```

### Shadow Applications (NEW — primary integration)
```
When user clicks "Generate Shadow Application" on a radar opportunity:
  1. Pass full RadarOpportunity to ShadowService
  2. ShadowService generates:
     - Hiring hypothesis (why this company needs this role)
     - Tailored CV (via existing edit_plan + render pipeline)
     - Strategy memo (2 paragraphs: positioning + approach)
     - Outreach messages (LinkedIn + email + follow-up)
  3. Shadow app uses signal context for richer hypothesis
  4. e.g., "TechCo raised Series C → they need VP Eng for MENA expansion"
  5. Costs 1 credit
```

### Intelligence Pack
```
When user clicks "Generate Pack" on a radar opportunity:
  1. Pre-fill NewApplication with company + role + any JD URL from sources
  2. Pass hidden market context as additional retrieval data
  3. Pack benefits from richer signal context
```

---

## File Structure

```
app/services/radar/
├── __init__.py
├── opportunity_radar.py       # Main orchestrator: collect → normalize → dedup → score → rank
├── adapters.py                # Source adapters (hidden_market, scout, signal_engine, email)
├── scorer.py                  # Heuristic scorer + Claude deep scorer
├── dedup.py                   # Normalization + merge logic
└── types.py                   # RadarInput, RadarOpportunity, ScoreBreakdown dataclasses

app/api/routes/
├── opportunities.py           # GET /api/v1/opportunities/radar

tests/e2e/
├── test_radar.py              # Radar endpoint + scoring tests
```

---

## Implementation Order

1. **`types.py`** — define RadarInput, RadarOpportunity, ScoreBreakdown dataclasses
2. **`adapters.py`** — Hidden Market + Scout Job + Signal Engine adapters (Email + LinkedIn are stubs returning `[]`)
3. **`dedup.py`** — normalize company/role, group, merge sources
4. **`scorer.py`** — heuristic scoring (profile_fit, signal_strength, recency, competition, conviction). Claude deep path as separate function.
5. **`opportunity_radar.py`** — orchestrator: load profile → call adapters → dedup → score → sort → return
6. **`opportunities.py`** — FastAPI route, cache logic, query param handling
7. **`test_radar.py`** — OpenClaw test coverage

---

## Relationship to Existing Code

| Existing | Relationship to Radar |
|----------|----------------------|
| `signal_engine.py` → `run_signal_engine()` | Radar calls this (or reads its cached `ScoutResult`), then normalizes via `adapt_signal_card()` |
| `scout.py` → `/scout/signals` | Radar reads the same `ScoutResult` rows. `/scout/signals` remains for backward compat but Dashboard migrates to `/opportunities/radar`. |
| `scout.py` → `/scout/jobs` | Radar calls `_adzuna()` + `_jsearch()` (or reads cached results) and normalizes via `adapt_scout_job()` |
| `hidden_market.py` (new, Day 1) | Radar reads `HiddenSignal` table rows and normalizes via `adapt_hidden_signal()` |
| `ProfileService` → active profile | Radar loads profile + preferences for fit scoring |
| `WhatsAppService` (new, Day 3) | WhatsApp alert flow calls Radar to get top opportunities |
| `EmailService` | Email digest flow calls Radar to get top opportunities |

The Radar does **not** replace the signal engine or scout — it sits above them as a ranking and unification layer.

---

## Phase 2 Extensions

When Email Intelligence ships:
1. Add `adapt_email_signal()` adapter (already stubbed)
2. Add "prior interaction" boost to conviction score
3. Add `email_intelligence` to `sources_active` in response
4. Radar reasoning includes: "You previously interacted with this company in 2024"

When LinkedIn integration ships:
1. Add `adapt_linkedin_signal()` adapter
2. Boost opportunities where user has mutual connections
3. Outreach hook uses mutual connection context
