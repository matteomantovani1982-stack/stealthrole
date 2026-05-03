# StealthRole Integration Matrix

Generated: 2026-05-01

## Legend

| Status | Meaning |
|--------|---------|
| **Built** | Code complete, backend + frontend wired, testable now |
| **Partial** | Backend exists but incomplete or frontend missing |
| **Missing** | Not implemented |
| **Needs OAuth** | Requires OAuth app registration + token flow |
| **Needs External API** | Requires third-party API key or account |
| **Testable Now** | Can be tested in current dev environment |

---

## 1. Gmail Integration

| Layer | Status | Details |
|-------|--------|---------|
| Backend — OAuth flow | **Built** | `app/services/email_integration/providers.py` → `GmailProvider` class. Google OAuth client_id/secret in config. Token encryption via Fernet. |
| Backend — Email scanning | **Built** | `GmailProvider.scan_inbox()` fetches recent emails, searches for job-related keywords, extracts recruiter signals. |
| Backend — Calendar sync | **Built** | `app/services/calendar/calendar_provider.py` → `fetch_google_calendar_events()`. Uses `calendar.readonly` scope. |
| Frontend — Connect flow | **Partial** | `app/api/routes/email_integration.py` exposes `/connect/google`, `/callback/google`. Frontend UI exists but needs OAuth app registered with Google. |
| Action executor — Send email | **Partial (Mock)** | `ActionExecutor._send_email()` is a stub returning mock results. Needs wiring to `GmailProvider` or SMTP. |
| **Overall** | **Partial — Needs OAuth** | Backend complete for read operations. Send is mock. Requires Google Cloud Console OAuth app + credentials. |
| **Testable Now** | With credentials | Set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` in `.env`. Read flow testable. Send remains mock. |

---

## 2. Outlook Integration

| Layer | Status | Details |
|-------|--------|---------|
| Backend — OAuth flow | **Built** | `app/services/email_integration/providers.py` → `OutlookProvider` class. Microsoft Graph API OAuth. |
| Backend — Email scanning | **Built** | `OutlookProvider.scan_inbox()` fetches via Microsoft Graph `/me/messages`. |
| Backend — Calendar sync | **Built** | `fetch_outlook_calendar_events()` in calendar_provider.py. Uses Graph API `/me/calendarView`. |
| Frontend — Connect flow | **Partial** | Routes exist (`/connect/outlook`, `/callback/outlook`). Needs Azure AD app registration. |
| Action executor — Send email | **Partial (Mock)** | Same mock as Gmail — `_send_email()` stub. |
| **Overall** | **Partial — Needs OAuth** | Backend complete for read. Send is mock. Requires Azure AD app registration + client credentials. |
| **Testable Now** | With credentials | Set Outlook OAuth vars in `.env`. Read flow testable. Send remains mock. |

---

## 3. WhatsApp

| Layer | Status | Details |
|-------|--------|---------|
| Backend — Message sending | **Built** | `app/services/whatsapp/service.py` → `WhatsAppService`. Uses Twilio WhatsApp API. Methods: `send_message()`, `send_radar_alert()`, `send_pack_ready()`, `send_shadow_ready()`. |
| Backend — Verification | **Built** | `app/services/whatsapp/verification.py` handles number verification. |
| Backend — Routes | **Built** | `app/api/routes/whatsapp.py` exposes endpoints. |
| Frontend — UI | **Partial** | Connected via API but no dedicated WhatsApp settings page in frontend. |
| **Overall** | **Built — Needs External API** | Fully functional with Twilio. Requires `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`. |
| **Testable Now** | With Twilio sandbox | Use Twilio WhatsApp sandbox for testing. Production requires approved Twilio number. |

---

## 4. LinkedIn Messaging

| Layer | Status | Details |
|-------|--------|---------|
| Backend — Message sync | **Built** | `app/api/routes/linkedin.py` → `sync_linkedin_messages()`. Models in `app/models/mutual_connection.py`. |
| Backend — Relationship engine | **Built** | `app/services/linkedin/relationship_engine.py` analyses connection strength. |
| Extension — Message capture | **Built** | `extension/src/linkedin-messages.js` captures messages from LinkedIn DOM. |
| Extension — Profile capture | **Built** | `extension/src/linkedin-profile.js` captures profile data. |
| Extension — Job capture | **Built** | `extension/src/linkedin-jobs.js` captures job postings. |
| Action executor — Send LinkedIn | **Partial (Mock)** | `ActionExecutor._send_linkedin_message()` is a stub. Real send requires extension relay (extension opens compose window, user confirms). |
| **Overall** | **Partial** | Read/capture works via extension. Send is mock. LinkedIn has no public messaging API — must go through extension UI automation or manual user action. |
| **Testable Now** | Extension capture only | Install extension, browse LinkedIn. Capture endpoints testable. Send remains manual/mock. |

---

## 5. Facebook Login

| Layer | Status | Details |
|-------|--------|---------|
| Backend | **Missing** | No Facebook OAuth provider, no config vars, no routes. |
| Frontend | **Missing** | No Facebook login button or flow. |
| **Overall** | **Missing** | Not implemented. Would require Facebook Developer App + OAuth flow similar to Google login. |
| **Testable Now** | No | Nothing to test. |

---

## 6. Google Login (OAuth)

| Layer | Status | Details |
|-------|--------|---------|
| Backend — OAuth flow | **Built** | `app/api/routes/auth.py` → `google_login()` + `google_login_url()`. Creates/links user account via Google OAuth. Provider stored as `"google"` on user model. |
| Backend — Token handling | **Built** | JWT tokens issued after Google auth. Refresh token rotation works. Password change blocked for OAuth-only users. |
| Frontend — Login button | **Built** | Google login button in frontend, redirects to Google OAuth consent, callback handled. |
| Config | **Partial** | `google_client_id` and `google_client_secret` in config.py but may share with Gmail integration. |
| **Overall** | **Built — Needs OAuth** | Fully implemented. Requires Google Cloud Console OAuth credentials. |
| **Testable Now** | With credentials | Set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`. Fully testable. |

---

## 7. Chrome Extension (Frontend)

| Layer | Status | Details |
|-------|--------|---------|
| Extension — Manifest | **Built** | `extension/manifest.json` — Manifest V3. |
| Extension — Core modules | **Built** | 15 source files covering: background service worker, popup UI, LinkedIn DOM scraping (profiles, jobs, connections, messages, search, intelligence, composer), autofill, token sync, config. |
| Extension — API integration | **Built** | `extension/src/config.js` + `token-sync.js` handle auth token sync with main app. Capture endpoints (`/extension/capture-*`) wired. |
| Extension — Intelligence overlay | **Built** | `extension/src/linkedin-intelligence.js` + `overlay.css` — shows signal data on LinkedIn pages. |
| Backend — Capture endpoints | **Built** | `app/api/routes/extension.py` — 3 capture endpoints (profile, job, company) with plan gating, rate limiting, and intelligence pipeline. |
| Backend — Pipeline trigger | **Built** | Extension capture now triggers quality filter + interpretation inline (P3 fix). |
| **Overall** | **Built** | Extension frontend + backend fully wired. Requires Chrome `chrome://extensions` developer mode to load unpacked. |
| **Testable Now** | Yes | Load unpacked extension, login to StealthRole, browse LinkedIn. All capture flows testable. |

---

## Summary Matrix

| Integration | Backend | Frontend/Extension | Auth Required | Testable Now |
|-------------|---------|-------------------|---------------|-------------|
| Gmail (read) | Built | Partial | Google OAuth | With creds |
| Gmail (send) | Mock | — | Google OAuth | No |
| Outlook (read) | Built | Partial | Azure AD OAuth | With creds |
| Outlook (send) | Mock | — | Azure AD OAuth | No |
| WhatsApp | Built | Partial | Twilio API | With sandbox |
| LinkedIn (capture) | Built | Built (extension) | Extension auth | Yes |
| LinkedIn (send) | Mock | — | No public API | No |
| Facebook Login | Missing | Missing | Facebook Dev App | No |
| Google Login | Built | Built | Google OAuth | With creds |
| Chrome Extension | Built | Built | Extension auth | Yes |
| Calendar (Google) | Built | Partial | Google OAuth | With creds |
| Calendar (Outlook) | Built | Partial | Azure AD OAuth | With creds |

---

## What's Testable Right Now (No External Credentials)

1. **Chrome Extension capture** — load unpacked, browse LinkedIn, signals created + pipeline runs
2. **Action engine** — generate/list/lifecycle/execute (mock channels)
3. **Quick-start** — keyword-based signal ranking from CV/role input
4. **Plan gating** — quota enforcement (action monthly limit, feature gates)
5. **Value/ROI engine** — insights endpoint with existing signal data
6. **Decision engine** — scoring through the full intelligence pipeline

## What Needs Credentials to Test

1. **Gmail/Outlook read** — Google/Azure OAuth credentials
2. **WhatsApp alerts** — Twilio sandbox account
3. **Google Login** — Google OAuth app (same as Gmail)
4. **Calendar sync** — shares OAuth with email providers

## What Needs Building

1. **Facebook Login** — full OAuth flow (backend + frontend)
2. **Email send** — wire `ActionExecutor._send_email()` to `GmailProvider`/`OutlookProvider` or SMTP
3. **LinkedIn send** — extension-mediated compose (no public API; extension opens LinkedIn compose, user confirms)
4. **Referral send** — wire to connection mapping + channel selection
