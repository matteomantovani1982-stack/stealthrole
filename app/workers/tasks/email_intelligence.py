"""
app/workers/tasks/email_intelligence.py

Deep email intelligence scan — fetches all emails, analyzes with Claude.
"""

import json
import asyncio

import structlog
from celery import Task

from app.workers.celery_app import celery

logger = structlog.get_logger(__name__)


@celery.task(
    bind=True,
    name="app.workers.tasks.email_intelligence.run_deep_scan",
    max_retries=1,
    soft_time_limit=900,
    time_limit=960,
)
def run_deep_scan(self: Task, user_id: str) -> dict:
    log = logger.bind(task_id=self.request.id, user_id=user_id)
    log.info("deep_email_scan_started")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_async_deep_scan(user_id))
        finally:
            loop.close()

        log.info("deep_email_scan_complete", **result)
        return result

    except Exception as e:
        log.error("deep_email_scan_failed", error=str(e))
        _mark_failed(user_id, str(e))
        raise self.retry(exc=e, countdown=120)


async def _async_deep_scan(user_id: str) -> dict:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.config import settings
    from app.models.email_account import EmailAccount
    from app.models.email_scan import EmailScan
    from app.services.email_integration.crypto import decrypt_token
    from app.services.email_integration.providers import get_provider
    from app.services.email_integration.intelligence_service import EmailIntelligenceService

    engine = create_async_engine(settings.database_url, pool_size=2)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        svc = EmailIntelligenceService(db)
        intel = await svc.start_scan(user_id)

        accounts = (await db.execute(
            select(EmailAccount).where(
                EmailAccount.user_id == user_id,
                EmailAccount.is_active == True,
            )
        )).scalars().all()

        if not accounts:
            intel.scan_status = "completed"
            intel.error_message = "No email accounts connected"
            await db.commit()
            return {"status": "no_accounts", "emails": 0}

        all_emails = []

        for account in accounts:
            try:
                access_token = decrypt_token(account.access_token_encrypted)
                provider = get_provider(account.provider)

                try:
                    refresh_token = decrypt_token(account.refresh_token_encrypted)
                    new_tokens = await provider.refresh_access(refresh_token)
                    access_token = new_tokens.access_token
                except Exception:
                    pass

                messages = await provider.fetch_all_messages(
                    access_token=access_token,
                    max_results=500,
                    years=3,
                )
                all_emails.extend(messages)
                logger.info("deep_scan_fetched", provider=account.provider, count=len(messages))

                for msg in messages:
                    try:
                        existing = await db.execute(
                            select(EmailScan).where(
                                EmailScan.email_account_id == account.id,
                                EmailScan.message_id == msg.message_id,
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue
                        db.add(EmailScan(
                            email_account_id=account.id,
                            message_id=msg.message_id,
                            email_from=str(msg.sender or ""),
                            email_subject=str(msg.subject or "(no subject)"),
                            email_date=msg.date,
                            email_snippet=str(msg.snippet or ""),
                        ))
                    except Exception:
                        continue

                account.total_scanned = len(messages)

            except Exception as e:
                logger.warning("deep_scan_account_failed", error=str(e))
                continue

        await db.flush()
        await db.commit()

        # Build summary and analyze with Claude
        summary = _build_summary(all_emails)
        logger.info("starting_claude_analysis", email_count=len(all_emails), summary_len=len(summary))

        analysis = await _analyze_with_claude(summary, len(all_emails))
        logger.info("claude_done", keys=list(analysis.keys()))

        intel = await svc.store_analysis(user_id, analysis, len(all_emails))
        logger.info("analysis_stored", status=intel.scan_status)

        return {
            "status": "complete",
            "total_emails": len(all_emails),
            "applications_found": analysis.get("applications_found", 0),
        }


def _build_summary(emails) -> str:
    from collections import Counter

    senders = Counter()
    domains = Counter()
    lines = []

    for em in emails:
        sender = str(em.sender or "")
        subject = str(em.subject or "")
        snippet = str(em.snippet or "")
        date_str = ""
        try:
            date_str = em.date.strftime('%Y-%m-%d') if em.date else ""
        except Exception:
            pass

        if "@" in sender:
            domain = sender.split("@")[-1].split(">")[0].strip().lower()
            domains[domain] += 1
        senders[sender] += 1
        lines.append(f"[{date_str}] {sender[:50]} | {subject[:80]} | {snippet[:80]}")

    top_senders = senders.most_common(30)
    top_domains = domains.most_common(20)

    return f"""EMAIL DATA — {len(emails)} emails from past 3 years

TOP SENDERS:
{chr(10).join(f'  {s}: {c}x' for s, c in top_senders)}

TOP DOMAINS:
{chr(10).join(f'  {d}: {c}x' for d, c in top_domains)}

EMAILS (most recent 250):
{chr(10).join(lines[:250])}
"""[:14000]


async def _analyze_with_claude(summary: str, total: int) -> dict:
    from app.services.llm.client import ClaudeClient
    from app.services.llm.router import LLMTask

    client = ClaudeClient(task=LLMTask.REPORT_PACK)

    system = "You are a strict career intelligence analyst. You ONLY report on actual job search activity. You never confuse business operations emails (vendors, government, utilities, subscriptions) with job hunting. Return only valid JSON."

    prompt = f"""Analyze this person's email history ({total} emails, 3 years). Your job is to find ONLY genuine job search activity.

{summary}

WHAT COUNTS AS JOB SEARCH (include these):
- Emails where this person APPLIED for a job (sent CV, cover letter, or application)
- Responses from RECRUITERS or HR about a job opening
- Interview scheduling emails (calendar invites for interviews)
- Job offer emails or salary negotiation
- Rejection emails from companies after applying
- LinkedIn recruiter InMail or job alert notifications
- Indeed, Glassdoor, Bayt, Naukri job notifications
- Headhunter/executive search firm outreach
- Networking emails specifically about job referrals

WHAT DOES NOT COUNT (exclude these completely):
- Business operations (vendors, suppliers, government filings like RAKEZ/DMCC/DED, utilities)
- Marketing newsletters and promotional emails
- Personal emails, social media notifications
- Banking, insurance, telecom correspondence
- SaaS product notifications (Stripe, AWS, GitHub, etc.)
- Subscription confirmations, receipts, shipping updates
- Company internal emails if they run a business

Be STRICT. If you're not confident an email is job-search related, do NOT count it.

Return this JSON:
{{
  "applications_found": <ONLY count confirmed job applications — be strict>,
  "total_companies_applied": <unique companies this person applied to for JOBS>,
  "total_responses": <responses from companies about JOB applications>,
  "response_rate_pct": <job application response rate>,
  "avg_response_days": <days for job-related responses>,
  "best_day_to_apply": "<day of week or null if insufficient data>",
  "best_time_to_apply": "<morning/afternoon/evening or null>",
  "avg_interviews_per_app": <ratio or 0>,
  "rejection_stage_distribution": {{"application": 0, "phone_screen": 0, "interview": 0, "final_round": 0}},
  "industry_breakdown": {{
    "<Industry>": {{"applied": 0, "interview": 0, "offer": 0, "rejected": 0}}
  }},
  "writing_style": {{
    "formality": "<Professional/Casual/Formal — based on job-related emails only>",
    "tone": "<Confident/Neutral/Tentative>",
    "greeting_style": "<typical greeting in job emails>",
    "closing_style": "<typical closing in job emails>",
    "common_phrases": ["phrase1", "phrase2", "phrase3"]
  }},
  "insights": {{
    "strengths": ["<3-5 strengths about their job search approach — ONLY from job-related evidence>"],
    "weaknesses": ["<2-3 job search weaknesses — be honest and specific>"],
    "recommendations": ["<3-5 actionable recommendations to improve their job search — specific, not generic>"],
    "career_trajectory": "<A paragraph about their job search trajectory: what roles they targeted, what industries, how active they were, what changed over time. If very few applications found, say so honestly and recommend using StealthRole to track properly.>"
  }},
  "key_contacts": [
    {{"name": "<name>", "company": "<company>", "role_context": "<recruiter/HR/hiring manager>", "email_count": 0}}
  ],
  "recruiter_activity": {{
    "inbound_recruiters": <count of actual recruiters who reached out about jobs>,
    "platforms_used": ["<LinkedIn/Indeed/Bayt — only if evidence found>"],
    "most_active_month": "<YYYY-MM or null>"
  }},
  "activity_timeline": {{
    "peak_months": ["<YYYY-MM — months with most job search activity>"],
    "quiet_months": ["<YYYY-MM>"],
    "trend": "<increasing/decreasing/stable>"
  }}
}}

CRITICAL RULES:
- Be STRICT about what counts as job search — vendors, government, utilities are NOT job search
- If you find very few actual job applications, report honestly with low numbers — do NOT inflate
- It's OK to return 0 for applications_found if there's no evidence of job hunting
- industry_breakdown should ONLY include industries the person applied to for JOBS
- key_contacts should ONLY include recruiters, HR contacts, or hiring managers — not vendors or service providers
- If the email history shows mostly business operations, say so in career_trajectory and recommend using StealthRole
- Return ONLY valid JSON, no markdown"""

    try:
        response, _meta = client.call_text(system, prompt)
        logger.info("claude_response_len", length=len(response))
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s\S]+\}', response)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        logger.error("claude_json_parse_failed", response_start=response[:200])
        return _fallback_analysis()
    except Exception as e:
        logger.error("claude_call_failed", error=str(e))
        return _fallback_analysis()


def _fallback_analysis() -> dict:
    return {
        "applications_found": 0,
        "total_companies_applied": 0,
        "total_responses": 0,
        "response_rate_pct": 0,
        "insights": {
            "strengths": ["Professional communication style"],
            "weaknesses": ["Limited job application data in scanned emails"],
            "recommendations": ["Use StealthRole to track applications systematically"],
            "career_trajectory": "Insufficient data for analysis. Connect more email accounts or scan a wider date range."
        },
        "writing_style": {
            "formality": "Professional", "tone": "Neutral",
            "greeting_style": "Hi,", "closing_style": "Best regards,",
            "common_phrases": []
        },
    }


def _mark_failed(user_id: str, error: str) -> None:
    from app.workers.db_utils import get_sync_db
    from app.models.email_intelligence import EmailIntelligence
    from sqlalchemy import select

    with get_sync_db() as db:
        result = db.execute(select(EmailIntelligence).where(EmailIntelligence.user_id == user_id))
        intel = result.scalar_one_or_none()
        if intel:
            intel.scan_status = "failed"
            intel.error_message = error[:500]
            db.commit()
