"""
app/services/llm/client.py

Claude API client for CareerOS.

Responsibilities:
- Single entry point for all Claude API calls
- Structured JSON output enforcement (prompt + parse)
- Retry with exponential backoff on rate limits / transient errors
- Token usage tracking (stored in JobStep.metadata_json)
- Cost estimation per call

Design constraints:
- Synchronous — runs inside Celery workers (no event loop)
- Never imports FastAPI, SQLAlchemy, or Celery
- Raises typed exceptions so task layer can decide retry vs fail

Two call modes:
  1. call_structured() — expects JSON response, parses and validates
  2. call_text()        — returns raw text (for future use / debugging)
"""

import json
import re
import time
from typing import Any, TypeVar
from pydantic import BaseModel

import anthropic
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from app.config import settings, should_skip_anthropic_api

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# ── Pricing constants (USD per million tokens) ─────────────────────────────
# Update when Anthropic changes pricing
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input_per_million": 15.00,
        "output_per_million": 75.00,
    },
    "claude-sonnet-4-6": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    "claude-haiku-4-5-20251001": {
        "input_per_million": 0.80,
        "output_per_million": 4.00,
    },
}

# ── Retry configuration ─────────────────────────────────────────────────────
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 60.0


def _estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate USD cost for a call. Returns 0.0 if model not in pricing table."""
    pricing = PRICING.get(model)
    if not pricing:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]
    return round(input_cost + output_cost, 6)


def _strip_json_fences(text: str) -> str:
    """
    Strip markdown code fences from LLM output.
    Claude sometimes wraps JSON in ```json ... ``` even when instructed not to.
    """
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3].rstrip()
    return text.strip()


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to repair truncated JSON from LLM output.
    Claude sometimes hits max_tokens and returns incomplete JSON.
    Also strips control characters that break json.loads.
    """
    text = _strip_json_fences(text)
    # Remove control characters (except \n \r \t) that Claude sometimes includes
    import re as _re
    text = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    text = text.strip()

    # If it parses fine, return as-is
    try:
        import json
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        pass

    # Try closing open brackets/braces
    # Count unmatched openers
    opens = 0
    open_sq = 0
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            opens += 1
        elif ch == '}':
            opens -= 1
        elif ch == '[':
            open_sq += 1
        elif ch == ']':
            open_sq -= 1

    # Remove trailing comma before closing
    text = text.rstrip().rstrip(',')

    # Close unclosed brackets
    text += ']' * max(0, open_sq)
    text += '}' * max(0, opens)

    return text


# ── Demo mode — realistic fake responses (no API credits needed) ───────────

_DEMO_EDIT_PLAN = {
    "keyword_match_score": 82,
    "headline_summary": {
        "new_headline": "Commercial Director | MENA Growth Operator | P&L Owner",
        "new_summary": "Results-driven commercial operator with 8+ years scaling operations across MENA. Track record of building high-performing teams and driving 3-5x revenue growth. Experienced in full P&L ownership, enterprise sales, and market expansion from Series A through Series B+.",
        "rationale": "Headline updated to mirror JD seniority signals. Summary leads with P&L ownership which is the primary hiring criterion."
    },
    "paragraph_edits": [
        {
            "paragraph_index": 3,
            "operation": "replace_text",
            "new_text": "Led regional expansion into 6 new GCC markets, generating $12M ARR and 200+ enterprise clients within 18 months of launch.",
            "rationale": "Added quantified outcomes — original lacked metrics."
        },
        {
            "paragraph_index": 5,
            "operation": "replace_text",
            "new_text": "Built and scaled 45-person cross-functional team across product, sales and operations — maintained 95% retention in year one.",
            "rationale": "Retention metric added to demonstrate team-building quality."
        }
    ],
    "keyword_additions": ["P&L ownership", "go-to-market strategy", "Series B scaling", "OKR framework", "ARR growth"],
    "sections_to_add": [],
    "positioning_note": "Strong match at 82%. Lead with commercial impact and P&L ownership throughout. The JD signals they want an operator who has owned revenue targets, not just managed teams. Add SaaS-specific language (ARR, NRR, churn) where possible.",
}

_DEMO_POSITIONING = {
    "positioning_headline": "The operator who builds the machine, then runs it.",
    "positioning_narrative": "You are not a consultant. You have owned P&L, hired teams, and stayed long enough to see the results. In a market full of project managers, you have built businesses. That is rare — especially for a company moving from Series A scrappiness to Series B scale.",
    "key_differentiators": [
        "MENA-native operator who understands commercial and cultural nuance that outside hires miss",
        "P&L owner, not just budget manager — accountable for outcomes, not activities",
        "Builder at scale — grew teams from 5 to 50+ without losing the culture",
    ],
    "angle_for_this_role": "Position yourself as the person who turns their Series B funding into a repeatable commercial engine. They have the product. They need the operator.",
    "what_to_emphasise_in_interview": [
        "The expansion strategy — show you have a clear 90-day plan",
        "Retention metrics — demonstrate you understand unit economics",
        "Team building philosophy — they are scaling fast and need someone who hires well",
    ],
}

_DEMO_REPORT_PACK = {
    "company": {
        "company_name": "Acme Corp",
        "hq_location": "Dubai, UAE",
        "business_description": "High-growth Series B enterprise SaaS company serving the GCC market. Founded 2019, raised $45M to date with strong product-market fit and 120% NRR.",
        "revenue_and_scale": "Est. $20M ARR, 150 employees, expanding rapidly across MENA.",
        "recent_news": ["Closed $30M Series B led by STV", "Expanding into Saudi Arabia Q1 2026", "Hiring aggressively across commercial and product teams"],
        "strategic_priorities": ["GCC market expansion", "Enterprise sales motion", "Product-led growth layer"],
        "culture_signals": ["Fast-paced execution culture", "Founders remain hands-on", "Quarterly OKRs reviewed by full leadership"],
        "competitor_landscape": "Competes with regional SaaS players and global entrants adapting to MENA compliance requirements.",
        "hiring_signals": ["3 senior commercial roles open", "New Saudi entity registered"],
        "red_flags": ["High sales team turnover based on LinkedIn data", "Three CFOs in four years"]
    },
    "role": {
        "role_title": "Commercial Director",
        "seniority_level": "Director / VP",
        "reporting_line": "Reports to CEO",
        "what_they_really_want": "An operator who has built and scaled a commercial team in the GCC and can own the full revenue motion — not just manage it.",
        "hidden_requirements": ["Experience hiring in Saudi Arabia", "Existing network in enterprise procurement", "Comfort with founder-led culture"],
        "hiring_manager_worries": ["Will they stay once they land?", "Can they operate without a big team around them?"],
        "keyword_match_gaps": ["SaaS metrics fluency", "ARR ownership", "Channel partnerships"],
        "positioning_recommendation": "Lead with P&L ownership and MENA team-building. Show you understand the Series B to C scaling challenge."
    },
    "salary": [
        {
            "title": "Commercial Director — UAE",
            "base_monthly_aed_low": 40000,
            "base_monthly_aed_high": 55000,
            "base_annual_aed_low": 480000,
            "base_annual_aed_high": 660000,
            "bonus_pct_low": 20,
            "bonus_pct_high": 40,
            "total_comp_note": "Equity (0.1–0.5%) typical at this stage. Push for equity if base is at lower end.",
            "source": "Market benchmarks + LinkedIn Salary + GCC compensation surveys",
            "confidence": "medium"
        }
    ],
    "networking": {
        "target_contacts": ["VP Commercial", "Head of Talent", "CEO / Co-founder", "Chief of Staff"],
        "warm_path_hypotheses": ["INSEAD / LBS alumni network", "Former colleagues now at the company", "Shared investors or advisors"],
        "linkedin_search_strings": ["Commercial Director Acme Corp", "VP Sales Dubai SaaS", "Head of Revenue MENA"],
        "outreach_template_hiring_manager": "Hi [Name], I have been following Acme Corp's growth — the Series B and Saudi expansion caught my attention. I have spent the last 8 years building commercial teams across the GCC and would love 15 minutes to explore whether there is a fit. Happy to share context on what I have been working on.",
        "outreach_template_alumni": "Hi [Name], I saw you joined Acme Corp — congrats on the move. I am exploring a similar step and would love to hear your perspective on the culture and what success looks like there. 15 minutes?",
        "outreach_template_recruiter": "Hi [Name], I am actively looking at senior commercial roles in GCC SaaS. I saw the Acme Corp opening and believe my background is a strong match. Can we connect?",
        "seven_day_action_plan": [
            "Day 1: Apply via portal and connect with Head of Talent on LinkedIn",
            "Day 2: Research the Saudi expansion announcement in depth",
            "Day 3: Send outreach to VP Commercial",
            "Day 4: Follow up with recruiter if no response",
            "Day 5: Identify and connect with 2 alumni at the company",
            "Day 6: Prepare your 90-day plan for the GCC expansion",
            "Day 7: Follow up on all outstanding outreach"
        ]
    },
    "application": {
        "positioning_headline": "The operator who builds the machine, then runs it.",
        "cover_letter_angle": "Open with the Saudi expansion. Show you understand what they are trying to build and that you have done it before. Keep it to 3 paragraphs — founders do not read long letters.",
        "interview_process": [
            {"stage": "Recruiter Screen", "format": "video", "who": "Head of Talent", "duration": "30 min", "what_to_expect": "Culture fit, salary expectations, availability. They are screening for MENA experience and startup pace tolerance."},
            {"stage": "Hiring Manager Deep Dive", "format": "video", "who": "CEO / Co-founder", "duration": "60 min", "what_to_expect": "Commercial strategy discussion. Expect to walk through a specific market entry plan. They want to see how you think, not just what you have done."},
            {"stage": "Case Study", "format": "in-person", "who": "VP Product + VP Sales", "duration": "90 min", "what_to_expect": "Live case: design a GTM strategy for Saudi expansion with constraints. They are assessing commercial thinking and cross-functional collaboration."},
            {"stage": "Founder / Board Interview", "format": "in-person", "who": "CEO + Board observer", "duration": "45 min", "what_to_expect": "Vision alignment and culture. They want to know you will stay and build, not just optimise and leave."}
        ],
        "question_bank": {
            "behavioural": [
                {"question": "Tell me about a time you entered a market where you had no existing relationships or infrastructure.", "why_they_ask": "Saudi expansion is their top priority — they need someone who has done cold market entry.", "your_story": "Use the GCC expansion at your previous role — 6 new markets, $12M ARR, 200+ clients in 18 months.", "key_points": ["How you identified the first 10 clients", "The local hiring strategy", "Revenue ramp timeline with specific numbers"]},
                {"question": "Describe a situation where you had to rebuild an underperforming sales team.", "why_they_ask": "LinkedIn data shows high sales turnover — they likely have this problem now.", "your_story": "Use the team restructuring story — 45-person team, 95% retention after changes.", "key_points": ["How you diagnosed the problem", "The changes you made to comp structure", "Retention metrics before and after"]},
                {"question": "Tell me about your biggest commercial failure and what you learned.", "why_they_ask": "Series B companies need leaders who can fail fast and course correct.", "your_story": "Use a real example — be honest about what went wrong and specific about the pivot.", "key_points": ["The decision that led to the failure", "How quickly you identified it", "The recovery and what changed"]}
            ],
            "business_case": [
                {"question": "We want to hit $50M ARR in Saudi within 24 months. Walk us through your approach.", "case_type": "market entry + growth strategy", "how_to_frame": "Start with market sizing, then go-to-market channels, then unit economics. Show you think in systems, not just tactics.", "watch_out": "Do not present a generic playbook. Reference Saudi-specific challenges — regulatory, Saudization, enterprise procurement cycles."},
                {"question": "Our enterprise sales cycle is 9 months. How would you cut it to 4?", "case_type": "operational problem", "how_to_frame": "Diagnose before prescribing. Ask about deal stages, where deals stall, and current team structure. Then propose 2-3 structural changes.", "watch_out": "Do not say 'just hire more SDRs'. They want strategic thinking about the pipeline architecture."}
            ],
            "situational": [
                {"question": "You discover our top-performing AE is also the most toxic team member. What do you do?", "what_they_want": "Culture vs revenue trade-off — they want someone who protects culture even at revenue cost.", "suggested_answer_angle": "Lead with the principle that culture scales, individuals do not. Give a specific framework: document, coach, set a deadline, act."},
                {"question": "The founders disagree with your commercial strategy. How do you handle it?", "what_they_want": "Can you influence without authority? Will you be a partner or just an executor?", "suggested_answer_angle": "Show you have navigated founder dynamics before. Use data to align, but respect that founders have context you do not."}
            ],
            "culture_and_motivation": [
                {"question": "Why leave a big company for a Series B?", "ideal_answer_angle": "Frame it as going back to building — you have done the big company thing and want to create something from scratch again. Reference their specific mission."},
                {"question": "What does success look like for you in 12 months?", "ideal_answer_angle": "Be specific to their context: Saudi office operational, X revenue milestone, team of Y hired and performing. Show you have already thought about this."}
            ]
        },
        "questions_to_ask_them": [
            {"question": "What does the current pipeline in Saudi look like, and what is the biggest bottleneck?", "why_powerful": "Shows you are already thinking about the problem. Forces them to reveal the real challenge."},
            {"question": "How involved are the founders in enterprise deal cycles today?", "why_powerful": "Signals you understand founder-led sales dynamics and are thinking about the transition."},
            {"question": "What happened with the last person in this role — or is this a new position?", "why_powerful": "Reveals whether this is a replacement (potential red flag) or growth (good sign). Shows you do diligence."}
        ],
        "interview_prep_themes": ["90-day commercial plan", "Team building in a new market", "How you have handled underperforming salespeople", "Your view on PLG vs enterprise sales"],
        "thirty_sixty_ninety": {
            "30": "Listen, map the current commercial motion, identify the 3 biggest gaps, and earn trust with the team.",
            "60": "Close your first enterprise deal independently. Hire one senior AE for the Saudi market.",
            "90": "Present a revised commercial strategy to the founders with pipeline data to back it up."
        },
        "risks_to_address": ["Perceived as too senior / expensive", "No direct SaaS background — reframe as advantage"],
        "differentiators": ["MENA-native operator with regional network", "P&L owner not just budget manager", "Track record of building teams that stay"]
    },
    "exec_summary": [
        "Strong match — 82% keyword alignment with room to add SaaS-specific language",
        "Company is at a critical Series B-to-C inflection point — high upside, high execution risk",
        "Salary range AED 480–660K base + 20–40% bonus + equity upside",
        "Key move: reference the Saudi expansion in your cover letter and interview",
        "Top networking target: VP Commercial — likely the hiring manager or has direct influence"
    ]
}



def _extract_from_prompt(prompt: str, hints: list[str], default: str) -> str:
    """Pull a value out of the prompt text using simple keyword scanning."""
    for hint in hints:
        m = re.search(hint + r"[:\s]+([^\n]{3,80})", prompt, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(".,")
    return default


def _extract_cv_and_jd_from_user_prompt(user_prompt: str) -> tuple[str, str]:
    """
    Split prompts from build_edit_plan_user_prompt / build_report_pack_user_prompt
    into CV text and JD text so demo mode can populate JSON from real uploads.
    """
    text = user_prompt or ""
    before, jd = text, ""
    parts = re.split(r"\n\s*JOB DESCRIPTION:\s*", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        before, jd = parts[0].strip(), parts[1].strip()
    for chop in ("\nPREFERENCES:", "\nTASK:", "\nRESEARCH DATA", "\nCANDIDATE'S KNOWN CONTACTS"):
        if chop in jd:
            jd = jd.split(chop)[0].strip()

    cv_block = before
    for marker in (
        "CANDIDATE CV (structured):",
        "CANDIDATE CV SUMMARY:",
        "CANDIDATE CV:",
    ):
        if marker in cv_block:
            cv_block = cv_block.split(marker, 1)[1].strip()
            break
    if "\nADDITIONAL CANDIDATE CONTEXT" in cv_block:
        cv_block = cv_block.split("\nADDITIONAL CANDIDATE CONTEXT")[0].strip()

    return cv_block.strip()[:24000], jd.strip()[:14000]


def _jd_keywords(jd: str, limit: int = 12) -> list[str]:
    if not jd.strip():
        return []
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", jd)
    bad = {
        "the", "and", "for", "with", "that", "this", "from", "have", "will", "your",
        "our", "are", "was", "been", "their", "they", "what", "when", "into", "than",
        "such", "about", "must", "can", "all", "any", "each", "which", "them", "who",
    }
    out: list[str] = []
    for w in words:
        wl = w.lower()
        if wl in bad or len(wl) < 3:
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def _cv_snippets(cv: str, max_chunks: int = 5, chunk_len: int = 320) -> list[str]:
    """Pull a few substantive lines from structured or plain CV text."""
    lines: list[str] = []
    for line in cv.splitlines():
        t = line.strip()
        if not t:
            continue
        t = re.sub(r"^\[P:\d+\]\s*", "", t)
        t = t.lstrip("•-–·*●◦▪\t ")
        if len(t) < 35:
            continue
        lines.append(t[:chunk_len])
        if len(lines) >= max_chunks:
            break
    if lines:
        return lines
    stripped = cv.strip()
    return [stripped[:chunk_len]] if stripped else []


def _indexed_paragraph_lines(cv: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in re.finditer(r"\[P:(\d+)\]\s*(.+)", cv):
        t = m.group(2).strip()
        if len(t) > 25:
            out.append((int(m.group(1)), t[:800]))
    return out


def _build_demo_edit_plan_from_prompt(user_prompt: str) -> dict:
    """Demo EditPlan grounded in the user's CV + JD blobs (no Anthropic)."""
    cv, jd = _extract_cv_and_jd_from_user_prompt(user_prompt)
    idx_paras = _indexed_paragraph_lines(cv)
    snips = _cv_snippets(cv)
    kw = _jd_keywords(jd, 15)
    jd_compact = " ".join(jd.split())[:500]

    edits: list[dict] = []
    for pin, text in idx_paras[:3]:
        edits.append(
            {
                "paragraph_index": pin,
                "operation": "replace_text",
                "new_text": text[:520],
                "rationale": (
                    f"Echo JD themes and keywords ({', '.join(kw[:6])}) while keeping your facts."
                    if kw
                    else "Sharpen metrics and leadership language for this posting (demo mode)."
                ),
            }
        )
    if not edits and snips:
        edits = [
            {
                "paragraph_index": 1,
                "operation": "replace_text",
                "new_text": snips[0][:520],
                "rationale": "Anchor the lead with your strongest quantified outcome.",
            }
        ]

    first_head = ""
    for line in cv.splitlines()[:25]:
        line = line.strip()
        if (
            line
            and not line.startswith("[")
            and "SECTION" not in line
            and len(line) < 140
        ):
            first_head = line
            break

    return {
        "keyword_match_score": min(96, 62 + min(30, len(kw) * 2)),
        "headline_summary": {
            "new_headline": (first_head[:90] if first_head else "Your headline | matched to this role")
            + (f" | JD: {', '.join(kw[:3])}" if kw else ""),
            "new_summary": (
                " ".join(
                    [
                        "Snapshot from your CV tailored to this JD (demo — set DEMO_MODE=false with API credits for full AI).",
                        snips[0] if snips else "",
                        f"Role asks for: {jd_compact[:360]}…" if jd_compact else "",
                    ]
                ).strip()[:1200]
            ),
            "rationale": "Weave JD keywords into headline and summary; keep every claim truthful.",
        },
        "paragraph_edits": edits,
        "keyword_additions": kw[:20] if kw else ["impact", "ownership", "cross-functional delivery"],
        "sections_to_add": [],
        "positioning_note": (
            f"Lead with outcomes that mirror: {jd_compact[:280]}…"
            if jd_compact
            else "Mirror language from the JD in your first page (demo note)."
        ),
    }


def _build_demo_report_pack(user_prompt: str) -> dict:
    """Demo intelligence pack: fill sections from parsed CV + JD text in the prompt."""
    cv, jd = _extract_cv_and_jd_from_user_prompt(user_prompt)
    company = _extract_from_prompt(
        user_prompt, ["company", "employer", "organisation", "organization"], "this employer"
    )
    role = _extract_from_prompt(
        user_prompt, ["role", "position", "title", "job title", "applying for"], "this role"
    )
    jd_short = " ".join(jd.split())[:900] if jd.strip() else _extract_from_prompt(
        user_prompt, ["JOB DESCRIPTION"], ""
    )
    snips = _cv_snippets(cv)
    kw = _jd_keywords(jd)
    cv_quote = " ".join(snips[:2])[:650] if snips else cv[:650]

    jd_for_role = jd_short if len(jd_short) > 80 else (user_prompt[:600].replace("\n", " "))

    return {
        "company": {
            "company_name": company[:120],
            "hq_location": "See JD / research (demo — no live crawl)",
            "business_description": (
                f"Derived from the job description you supplied: {jd_for_role[:520]}…"
            ),
            "revenue_and_scale": "Infer scale from JD and careers page when not in demo.",
            "recent_news": [
                "DEMO_MODE: company news is not web-fetched. Add API access for live intel.",
                jd_for_role[:200] + "…" if len(jd_for_role) > 40 else "Use JD text for priorities.",
            ],
            "strategic_priorities": [
                f"JD signals: {jd_for_role[:220]}…",
                "Align your stories to these themes in interviews.",
            ],
            "culture_signals": [
                f"From posting tone: {jd_for_role[80:300]}…"
                if len(jd_for_role) > 160
                else "Read JD for cultural hints (collaboration, pace, ownership)."
            ],
            "competitor_landscape": "Benchmark peers named in JD or common in that sector (demo placeholder).",
            "hiring_signals": [f"Keywords to mirror: {', '.join(kw[:8])}" if kw else "Mirror JD language."],
            "red_flags": ["Review employer reviews and leadership stability outside demo."],
        },
        "role": {
            "role_title": role[:120],
            "seniority_level": "As stated in JD",
            "reporting_line": "See JD for line management / matrix",
            "what_they_really_want": jd_for_role[:700] + ("…" if len(jd_for_role) > 700 else ""),
            "hidden_requirements": [
                "Unstated: culture fit and pace — read between lines in JD.",
                "Map your proof points: " + (cv_quote[:300] + "…"),
            ],
            "hiring_manager_worries": [
                "Can this hire deliver in the first 90 days?",
                "Evidence you have done this before in similar context — use: " + cv_quote[:200] + "…",
            ],
            "keyword_match_gaps": [
                f"JD emphasises: {', '.join(kw[:10])}" if kw else "Compare JD must-haves to your CV.",
            ],
            "positioning_recommendation": (
                "Lead with: " + (snips[0][:200] + "…") if snips else "Lead with strongest quantified outcomes."
            ),
        },
        "salary": [
            {
                "title": role[:80],
                "base_annual_aed_low": 360000,
                "base_annual_aed_high": 620000,
                "bonus_pct_low": 15,
                "bonus_pct_high": 35,
                "total_comp_note": "Demo range — calibrate to role level and region.",
                "source": "Demo heuristic",
                "confidence": "low",
            }
        ],
        "networking": {
            "target_contacts": ["Hiring manager", "Recruiter", "Peer in function", "Alumni"],
            "warm_path_hypotheses": [
                "Peers at target company",
                "School / programme alumni",
                "Shared investors or advisors",
            ],
            "linkedin_search_strings": [
                f"{role} {company}",
                f"{company} hiring {role}",
            ],
            "outreach_template_hiring_manager": (
                f"Hi [Name] — I applied for {role} at {company}. My background includes: {cv_quote[:200]}… "
                f"Happy to share how I would approach the priorities in the posting."
            ),
            "outreach_template_alumni": (
                "Hi [Name] — I noticed you are at [Company]. I am in process for a role there "
                "and would value 10–15 minutes of your perspective."
            ),
            "outreach_template_recruiter": (
                f"Hi [Name] — re: {role} at {company}. Key fit: {cv_quote[:180]}… Open to a short call."
            ),
            "seven_day_action_plan": [
                "Day 1: Submit application; message recruiter with 2-line fit summary from your CV.",
                "Day 2: Map JD phrases to your bullet points; update CV headline if needed.",
                "Day 3: Short list 5 stakeholders; send tailored notes.",
                "Day 4–5: Follow-ups; prep 3 stories from: " + (snips[0][:120] + "…" if snips else "your CV."),
                "Day 6: Mock interview against JD themes.",
                "Day 7: Thank-you and pipeline next roles.",
            ],
        },
        "application": {
            "positioning_headline": (
                f"{snips[0][:90]}…" if snips else f"Fit for {role} at {company}"
            ),
            "cover_letter_angle": (
                f"Open with the clearest overlap between the JD and your proof: {cv_quote[:300]}…"
            ),
            "interview_process": [
                {
                    "stage": "Screen / first call",
                    "format": "video",
                    "who": "Recruiter or HM",
                    "duration": "30–45 min",
                    "what_to_expect": "Motivation, scope, examples. Prep stories from: " + (snips[0][:140] + "…" if snips else "CV."),
                },
                {
                    "stage": "Deep dive",
                    "format": "video",
                    "who": "Hiring manager + panel",
                    "duration": "60 min",
                    "what_to_expect": f"Expect questions on: {jd_for_role[:200]}…",
                },
            ],
            "question_bank": {
                "behavioural": [
                    {
                        "question": f"Tell me about a time you delivered what this JD describes: {jd_for_role[:160]}…",
                        "why_they_ask": "Maps posting to past behaviour.",
                        "your_story": f"Use material from your CV: {snips[0][:260]}…" if snips else "Prepare CAR stories from last 3 roles.",
                        "key_points": [s[:120] for s in snips[:3]] if snips else ["Metrics", "Stakeholders", "Outcome"],
                    }
                ],
                "business_case": [
                    {
                        "question": f"How would you prioritise in year one given: {jd_for_role[:180]}…?",
                        "case_type": "prioritisation",
                        "how_to_frame": "Problem → options → trade-offs → KPIs.",
                        "watch_out": "Tie to JD language and your CV scale.",
                    }
                ],
                "situational": [
                    {
                        "question": "What would you do in the first 90 days?",
                        "what_they_want": "Clarity and practicality.",
                        "suggested_answer_angle": "Listen → quick wins → 90-day plan aligned to JD priorities.",
                    }
                ],
                "culture_and_motivation": [
                    {
                        "question": f"Why {company} and why this move now?",
                        "ideal_answer_angle": "Connect their mission to your track record (see CV excerpt).",
                    }
                ],
            },
            "questions_to_ask_them": [
                {
                    "question": "How is success measured for this role in the first 12 months?",
                    "why_powerful": "Surfaces real expectations behind the JD.",
                },
                {
                    "question": "What is the hardest problem the team needs solved this year?",
                    "why_powerful": "Shows you think in their priorities.",
                },
            ],
            "interview_prep_themes": kw[:12] if kw else ["Impact", "Collaboration", "Execution"],
            "thirty_sixty_ninety": {
                "30": "Map stakeholders; align on priorities from JD; deliver one visible win.",
                "60": "Run initiatives tied to: " + jd_for_role[:120] + "…",
                "90": "Report outcomes vs plan; propose next horizon.",
            },
            "risks_to_address": [
                "Any gap between JD 'must haves' and CV — prepare crisp mitigation.",
            ],
            "differentiators": [s[:160] for s in snips[:4]] if snips else ["Your distinct outcomes"],
        },
        "exec_summary": [
            f"JD focus: {jd_for_role[:220]}…" if jd_for_role else "Align to posting.",
            f"Your evidence: {cv_quote[:260]}…" if cv_quote else "Pull proof from uploaded CV.",
            f"Keywords to echo: {', '.join(kw[:12])}" if kw else "Mirror JD phrasing.",
            "DEMO_MODE: set DEMO_MODE=false with Anthropic credits for full-model packs.",
        ],
    }


def _build_demo_outreach(user_prompt: str) -> dict:
    """Demo outreach grounded in extracted CV/JD."""
    cv, jd = _extract_cv_and_jd_from_user_prompt(user_prompt)
    company = _extract_from_prompt(user_prompt, ["company", "COMPANY"], "the company")
    role = _extract_from_prompt(user_prompt, ["role", "TARGET ROLE", "position"], "the role")
    snips = _cv_snippets(cv)
    hook = snips[0][:220] if snips else jd[:220].replace("\n", " ")
    return {
        "linkedin_note": (
            f"Hi — {role} at {company} is a tight match. From my background: {hook}… "
            f"Happy to compare notes in 15 minutes."
        ),
        "cold_email": (
            f"Subject: {role} — {hook[:48]}…\n\n"
            f"I am applying for the {role} role. Relevant experience: {hook}… "
            f"Open to a brief call.\n\nBest,"
        ),
        "follow_up": (
            f"Following up on {role} at {company} — still keen. Highlights: {hook[:140]}…"
        ),
    }


def _build_demo_positioning(user_prompt: str) -> dict:
    """Demo positioning texts built from user's CV/JD excerpts."""
    cv, jd = _extract_cv_and_jd_from_user_prompt(user_prompt)
    role = _extract_from_prompt(user_prompt, ["role", "position", "title", "applying for"], "this role")
    company = _extract_from_prompt(user_prompt, ["company", "employer", "organisation"], "the company")
    snips = _cv_snippets(cv)
    kw = _jd_keywords(jd)
    jd_compact = " ".join(jd.split())[:380]

    return {
        "positioning_headline": (snips[0][:96] + "…") if snips else f"Evidence-led fit for {role}",
        "positioning_narrative": (
            "Positioning (demo — from your uploads): your CV shows "
            + (snips[0][:320] + "… " if snips else "")
            + (
                f"The role asks for: {jd_compact}… Set DEMO_MODE=false for full AI narration."
                if jd_compact
                else ""
            ).strip()
        )[:1600],
        "key_differentiators": [
            s[:160] for s in snips[:3]
        ] if snips else ["Quantified outcomes", "Scope and scale", "Leadership cadence"],
        "angle_for_this_role": (
            f"Translate your track record ({snips[0][:120]}…) into outcomes they advertise: {', '.join(kw[:8])}"
            if snips and kw
            else f"Map your strongest wins to what {company} lists in the posting."
        ),
        "what_to_emphasise_in_interview": [
            f"Keywords from JD: {', '.join(kw[:10])}" if kw else "Priorities spelled out in the posting",
            snips[0][:140] + "…" if snips else "Top career proof points",
            "Evidence of dealing with ambiguity and pace",
        ],
    }


def _make_demo_result(data: dict) -> "LLMCallResult":
    import json as _j
    return LLMCallResult(
        content=_j.dumps(data),
        model="demo-mode",
        input_tokens=0,
        output_tokens=0,
        duration_seconds=0.0,
    )


class LLMCallResult:
    """
    Result of a single Claude API call.
    Contains the parsed output plus usage metadata for cost tracking.
    """

    def __init__(
        self,
        content: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        duration_seconds: float,
    ) -> None:
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.duration_seconds = duration_seconds
        self.cost_usd = _estimate_cost_usd(model, input_tokens, output_tokens)

    def to_metadata(self) -> dict:
        """Serialise to dict for storage in JobStep.metadata_json."""
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
        }


class ClaudeClient:
    """
    Synchronous Claude API client with model routing and caching.

    Instantiate once per Celery task — do not share across tasks.
    Thread-safe (each task creates its own client instance).

    Model selection (in priority order):
      1. Explicit model= parameter (override)
      2. task= parameter → resolved via LLM router
      3. settings.claude_model (global default)
    """

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
        task: str | None = None,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._task = task

        # Model selection: explicit > task-routed > global default
        if model:
            self.model = model
        elif task:
            from app.services.llm.router import get_model_for_task
            self.model = get_model_for_task(task)
        else:
            self.model = settings.claude_model

        self.max_tokens = max_tokens or settings.claude_max_tokens

    def call_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float = 0.2,
    ) -> tuple[T, LLMCallResult]:
        """
        Call Claude and parse the response as a Pydantic model.

        Instructs Claude to return ONLY valid JSON matching the schema.
        Retries on rate limits and transient API errors.

        Args:
            system_prompt: System-level instructions (persona, format rules)
            user_prompt:   The actual request content (CV + JD + instructions)
            schema:        Pydantic model class to parse the JSON into
            temperature:   Sampling temperature (lower = more deterministic)

        Returns:
            Tuple of (parsed_schema_instance, LLMCallResult with metadata)

        Raises:
            ValueError:    if the response cannot be parsed as valid JSON
                           or doesn't match the schema (after retries)
            RuntimeError:  if max retries exceeded on API errors
        """
        raw_result = self._call_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )

        # Parse and validate JSON (with repair for truncated output)
        try:
            cleaned = _repair_truncated_json(raw_result.content)
            data = json.loads(cleaned)
            parsed = schema.model_validate(data)
        except json.JSONDecodeError as e:
            logger.error(
                "llm_json_parse_error",
                error=str(e),
                raw_content=raw_result.content[:500],
            )
            raise ValueError(
                f"Claude returned invalid JSON: {e}. "
                f"Raw content (first 200 chars): {raw_result.content[:200]}"
            ) from e
        except Exception as e:
            logger.error(
                "llm_schema_validation_error",
                schema=schema.__name__,
                error=str(e),
            )
            raise ValueError(
                f"Claude response didn't match schema {schema.__name__}: {e}"
            ) from e

        logger.info(
            "llm_call_structured_complete",
            model=raw_result.model,
            schema=schema.__name__,
            tokens=raw_result.input_tokens + raw_result.output_tokens,
            cost_usd=raw_result.cost_usd,
        )

        return parsed, raw_result

    def call_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> tuple[str, LLMCallResult]:
        """
        Call Claude and return raw text response.
        Checks cache first for deterministic tasks.
        Falls back to next model tier on failure.
        """
        # Check cache for deterministic tasks
        if self._task:
            from app.services.llm.cache import get_cached, set_cached
            cached = get_cached(self._task, self.model, system_prompt, user_prompt)
            if cached is not None:
                return cached, LLMCallResult(
                    content=cached, model=f"{self.model}:cached",
                    input_tokens=0, output_tokens=0, duration_seconds=0.0,
                )

        try:
            result = self._call_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
        except Exception as e:
            # Fallback: try next model tier
            result = self._try_fallback(system_prompt, user_prompt, temperature, e)

        # Cache the result for deterministic tasks
        if self._task:
            from app.services.llm.cache import set_cached
            set_cached(self._task, self.model, system_prompt, user_prompt, result.content)

        return result.content, result

    def _try_fallback(
        self, system_prompt: str, user_prompt: str,
        temperature: float, original_error: Exception,
    ) -> LLMCallResult:
        """Try the next model tier if the current one fails."""
        from app.services.llm.router import get_fallback_model
        fallback = get_fallback_model(self.model)
        if fallback:
            logger.warning(
                "llm_fallback_triggered",
                original_model=self.model,
                fallback_model=fallback,
                error=str(original_error),
            )
            old_model = self.model
            self.model = fallback
            try:
                return self._call_with_retry(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                )
            finally:
                self.model = old_model  # Restore original
        raise original_error


    # Alias for call_text — used when expecting raw JSON (e.g. PositioningStrategy)
    call_raw = call_text

    _DEMO_RESPONSES: dict[str, dict] = {
        "EditPlan": _DEMO_EDIT_PLAN,
        "PositioningStrategy": _DEMO_POSITIONING,
        "ReportPack": _DEMO_REPORT_PACK,
        "default": _DEMO_REPORT_PACK,
    }

    def _demo_response(self, schema_name: str) -> "LLMCallResult":
        """Return realistic fake data for demo/testing without hitting Claude API."""
        import json as _json

        fake_content = self._DEMO_RESPONSES.get(schema_name, self._DEMO_RESPONSES["default"])
        return LLMCallResult(
            content=_json.dumps(fake_content) if isinstance(fake_content, dict) else fake_content,
            model="demo-mode",
            input_tokens=0,
            output_tokens=0,
            duration_seconds=0.0,
        )

    def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> LLMCallResult:
        """
        Core API call with exponential backoff retry.

        Retries on:
          - RateLimitError (429) — back off and retry
          - APIConnectionError  — transient network issue
          - APITimeoutError     — request timed out

        Does NOT retry on:
          - 400 Bad Request   — prompt issue, won't fix itself
          - 401 Unauthorized  — bad API key
          - 4xx other than 429
        """
        last_exception: Exception | None = None

        # Demo / local dev — skip real API (matches profile_import + health)
        if should_skip_anthropic_api():
            if "CV Tailor" in system_prompt:
                return _make_demo_result(_build_demo_edit_plan_from_prompt(user_prompt))
            elif "Intelligence Analyst" in system_prompt:
                return _make_demo_result(_build_demo_report_pack(user_prompt))
            elif "CareerOS Intelligence" in system_prompt:
                return _make_demo_result(_build_demo_positioning(user_prompt))
            elif "outreach" in system_prompt.lower() or "linkedin" in system_prompt.lower():
                return _make_demo_result(_build_demo_outreach(user_prompt))
            else:
                return _make_demo_result(_build_demo_report_pack(user_prompt))

        for attempt in range(MAX_RETRIES + 1):
            try:
                start_time = time.monotonic()

                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                duration = time.monotonic() - start_time

                # Extract text content from response
                content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        content += block.text

                return LLMCallResult(
                    content=content,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    model=response.model,
                    duration_seconds=duration,
                )

            except RateLimitError as e:
                last_exception = e
                if attempt >= MAX_RETRIES:
                    break
                backoff = min(
                    BASE_BACKOFF_SECONDS * (2 ** attempt),
                    MAX_BACKOFF_SECONDS,
                )
                logger.warning(
                    "llm_rate_limit",
                    attempt=attempt + 1,
                    backoff_seconds=backoff,
                )
                time.sleep(backoff)

            except (APIConnectionError, APITimeoutError) as e:
                last_exception = e
                if attempt >= MAX_RETRIES:
                    break
                backoff = min(
                    BASE_BACKOFF_SECONDS * (2 ** attempt),
                    MAX_BACKOFF_SECONDS,
                )
                logger.warning(
                    "llm_transient_error",
                    error_type=type(e).__name__,
                    attempt=attempt + 1,
                    backoff_seconds=backoff,
                )
                time.sleep(backoff)

            except APIStatusError as e:
                # 4xx errors other than 429 — don't retry
                logger.error(
                    "llm_api_status_error",
                    http_status=e.status_code,
                    error=str(e),
                )
                raise RuntimeError(
                    f"Claude API error {e.status_code}: {e.message}"
                ) from e

        # Max retries exceeded
        raise RuntimeError(
            f"Claude API call failed after {MAX_RETRIES} retries. "
            f"Last error: {last_exception}"
        ) from last_exception
