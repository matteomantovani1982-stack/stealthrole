"""
app/services/shadow/shadow_service.py

ShadowService — orchestrates Shadow Application generation.

Accepts a radar opportunity or manual input and produces:
  1. Hiring hypothesis (why this company needs this role)
  2. Tailored CV (reuses existing edit_plan → render pipeline)
  3. Strategy memo (positioning + approach)
  4. Outreach messages (LinkedIn + email + follow-up)

Called from the Celery task (shadow_gen.py) in a synchronous context.
"""

import json
import re

import structlog

from app.config import settings
from app.services.shadow.shadow_schema import OutreachMessages, ShadowPack

logger = structlog.get_logger(__name__)


def _cap_confidence(company: str, signal_context: str, llm_confidence: float) -> float:
    """
    Cap confidence based on input quality signals.

    The LLM often returns high confidence regardless of input quality.
    This function enforces reality-based caps.
    """
    import re

    name = company.strip().lower()
    ctx = (signal_context or "").strip().lower()

    # 1. Fictional/nonsense company name (random characters, very short, no vowels)
    has_vowels = bool(re.search(r'[aeiou]', name))
    is_short_gibberish = len(name) < 4 and not has_vowels
    is_long_gibberish = len(name) > 5 and not re.search(r'[aeiou]{1}.*[aeiou]', name)
    if is_short_gibberish or is_long_gibberish:
        return min(llm_confidence, 0.2)

    # 2. Well-known defunct companies
    defunct = {"blockbuster", "blockbuster video", "toys r us", "compaq", "kodak",
               "blackberry", "nokia mobile", "myspace", "friendster", "enron",
               "lehman brothers", "bear stearns", "pan am", "woolworths", "borders"}
    if name in defunct or any(d in name for d in defunct):
        return min(llm_confidence, 0.15)

    # 3. No verifiable signal context (nonsense or lorem ipsum)
    if "lorem ipsum" in ctx or "asdf" in ctx or len(ctx) < 10:
        return min(llm_confidence, 0.3)

    # 4. Unknown company (not in any recognizable pattern) — moderate cap
    # Well-known companies get no cap. For unknown ones, cap at 0.7
    well_known = {"google", "meta", "amazon", "apple", "microsoft", "netflix",
                  "uber", "careem", "noon", "tabby", "anghami", "kitopi", "salla",
                  "talabat", "deliveroo", "swvl", "spotify", "airbnb", "stripe",
                  "openai", "anthropic", "tesla", "nvidia", "salesforce"}
    if name not in well_known and not any(wk in name for wk in well_known):
        return min(llm_confidence, 0.7)

    return llm_confidence


def _extract_json(raw: str) -> dict:
    """
    Extract the first valid JSON object from Claude's response.

    Handles: markdown fences, trailing text after JSON, leading text before JSON.
    """
    text = raw.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { and match to closing }
    start = text.find("{")
    if start == -1:
        logger.warning("extract_json_no_object", preview=text[:200])
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    logger.warning("extract_json_parse_failed", preview=text[start:start+200])
                    return None

    logger.warning("extract_json_unbalanced", preview=text[:200])
    return None


# ── Prompts ──────────────────────────────────────────────────────────────────

HYPOTHESIS_SYSTEM = """You are a senior executive recruiter with 20 years of experience in MENA markets.

Given a company signal (funding, expansion, leadership change, etc.) and a candidate profile,
generate a hiring hypothesis: WHY this company likely needs a specific role and why THIS candidate is a fit.

CRITICAL RULES:

1. ROLE PRIORITY: If the user specifies "LIKELY ROLES" in the input, you MUST use one of those
   roles as the hypothesis_role. Do NOT substitute a different function.

2. REALITY CHECK — THIS IS THE MOST IMPORTANT RULE:
   - Do NOT treat the user's signal context as verified fact.
   - If the company name looks fictional, random, or nonsensical → set confidence to 0.1-0.2
     and say so in the reasoning ("company name appears fictional").
   - If the company is well-known to be defunct, bankrupt, or no longer operating → set
     confidence to 0.1-0.2 and note "company is defunct/bankrupt" in reasoning.
   - If the signal claims something extraordinary (e.g., "500 new stores" for a company with
     no known retail presence) → flag it as unverified in the hypothesis.
   - NEVER present unverified user claims as confirmed facts. Use language like "if confirmed"
     or "based on the reported signal" instead of asserting the signal as truth.

3. CONFIDENCE SCORING:
   - 0.8-1.0: ONLY for well-known, active companies where the signal is plausible
   - 0.5-0.7: Known company, plausible signal, but unverified
   - 0.3-0.4: Unknown company or unverifiable signal
   - 0.1-0.2: Fictional company, defunct company, or nonsensical input

Always return valid JSON. Never refuse. Work with what you have — but be honest about uncertainty.

Return ONLY JSON:
{
  "hypothesis_role": "use one of the LIKELY ROLES specified, or infer if none given",
  "hiring_hypothesis": "2-3 paragraphs. Use 'if confirmed' language for unverified claims. Flag defunct/fictional companies.",
  "confidence": 0.0-1.0,
  "reasoning": "1 sentence on why this candidate matches. Flag if company appears fictional or defunct."
}

Be specific. Reference the signal. Don't be generic."""

STRATEGY_MEMO_SYSTEM = """You are a career strategist advising a senior professional on how to approach a company
that hasn't posted a job yet.

Given the hiring hypothesis, candidate profile, and company signal, write a strategy memo.

Return ONLY JSON:
{
  "strategy_memo": "2-3 paragraphs. First paragraph: positioning angle (how to frame yourself). Second paragraph: approach strategy (who to contact, what to say, timing). Third paragraph: what to prepare (talking points, proof points)."
}

Be concrete. Reference the candidate's actual experience. No filler."""

OUTREACH_SYSTEM = """You are an expert at writing cold outreach messages for senior professionals.

Given the hiring hypothesis, strategy memo, and candidate profile, generate three messages.

CRITICAL TRUST RULES:
- Do NOT state unverified claims as facts. If the signal mentions funding, expansion, or
  hiring — use hedged language: "I understand you may be expanding" or "following reports
  of your recent growth" — NOT "saw you raised $100M" or "saw your 500-store expansion."
- If you don't recognize the company, use generic professional framing rather than
  inventing specific claims about the company's activities.
- The messages will be sent to REAL people. Incorrect claims damage the sender's credibility.
- When in doubt, focus on the CANDIDATE's value proposition rather than making claims about
  the company's situation.

Return ONLY JSON:
{
  "linkedin_note": "Max 280 chars. Use hedged language for unverified signals. Focus on candidate value, not company claims.",
  "cold_email": "3-paragraph cold email. Subject line first. Reference the opportunity context carefully — don't state unverified claims as fact.",
  "follow_up": "Follow-up for 1 week later. 2-3 sentences. Reference original message."
}"""


class ShadowGenerator:
    """
    Generates Shadow Application Pack components via Claude Haiku.

    Each method is independent and can be called separately.
    The Celery task orchestrates the full pipeline.
    """

    def generate_hypothesis(
        self,
        company: str,
        signal_type: str,
        signal_context: str,
        likely_roles: list[str],
        profile_summary: str,
    ) -> dict:
        """Generate hiring hypothesis via Claude Haiku."""
        from app.services.llm.client import ClaudeClient

        user_prompt = (
            f"COMPANY: {company}\n"
            f"SIGNAL TYPE: {signal_type}\n"
            f"SIGNAL CONTEXT: {signal_context}\n"
            f"LIKELY ROLES: {', '.join(likely_roles)}\n\n"
            f"CANDIDATE PROFILE:\n{profile_summary}\n\n"
            f"Generate the hiring hypothesis."
        )

        from app.services.llm.router import LLMTask
        client = ClaudeClient(task=LLMTask.SHADOW_HYPOTHESIS, max_tokens=4000)
        raw_text, result = client.call_raw(
            system_prompt=HYPOTHESIS_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.3,
        )

        data = _extract_json(raw_text)

        if data is None:
            # Claude refused or returned prose — build a minimal fallback
            logger.warning("hypothesis_json_failed_using_fallback", company=company)
            data = {
                "hypothesis_role": likely_roles[0] if likely_roles else "Senior Role",
                "hiring_hypothesis": f"{company} shows {signal_type} signals suggesting potential hiring. Specific role inference requires more company context.",
                "confidence": 0.3,
                "reasoning": "Limited data — hypothesis based on signal pattern only.",
            }

        logger.info(
            "hypothesis_generated",
            company=company,
            role=data.get("hypothesis_role"),
            tokens=result.input_tokens + result.output_tokens,
            cost=result.cost_usd,
        )
        return data

    def generate_strategy_memo(
        self,
        company: str,
        hiring_hypothesis: str,
        profile_summary: str,
        signal_context: str,
    ) -> str:
        """Generate strategy memo via Claude."""
        from app.services.llm.client import ClaudeClient
        from app.services.llm.router import LLMTask

        user_prompt = (
            f"COMPANY: {company}\n"
            f"HIRING HYPOTHESIS: {hiring_hypothesis}\n"
            f"SIGNAL CONTEXT: {signal_context}\n\n"
            f"CANDIDATE PROFILE:\n{profile_summary}\n\n"
            f"Write the strategy memo."
        )

        client = ClaudeClient(task=LLMTask.STRATEGY_MEMO, max_tokens=4000)
        raw_text, result = client.call_raw(
            system_prompt=STRATEGY_MEMO_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.3,
        )

        data = _extract_json(raw_text)

        logger.info(
            "strategy_memo_generated",
            company=company,
            tokens=result.input_tokens + result.output_tokens,
        )
        if data is None or "strategy_memo" not in data:
            logger.warning("strategy_memo_json_failed_using_raw", company=company)
            # Use the raw text as the memo — Claude probably returned prose directly
            return raw_text.strip()[:2000] if raw_text.strip() else f"Approach {company} by highlighting your relevant experience and referencing the {signal_context[:100]} signal."
        return data["strategy_memo"]

    def generate_outreach(
        self,
        company: str,
        hypothesis_role: str,
        hiring_hypothesis: str,
        strategy_memo: str,
        profile_summary: str,
        tone: str = "confident",
    ) -> OutreachMessages:
        """Generate outreach messages via Claude Haiku."""
        from app.services.llm.client import ClaudeClient

        user_prompt = (
            f"COMPANY: {company}\n"
            f"TARGET ROLE: {hypothesis_role}\n"
            f"HIRING HYPOTHESIS: {hiring_hypothesis}\n"
            f"STRATEGY MEMO: {strategy_memo}\n"
            f"TONE: {tone}\n\n"
            f"CANDIDATE PROFILE:\n{profile_summary}\n\n"
            f"Generate the outreach messages."
        )

        from app.services.llm.router import LLMTask
        client = ClaudeClient(task=LLMTask.OUTREACH, max_tokens=4000)
        raw_text, result = client.call_raw(
            system_prompt=OUTREACH_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.4,
        )

        data = _extract_json(raw_text)

        logger.info(
            "outreach_generated",
            company=company,
            tokens=result.input_tokens + result.output_tokens,
        )
        if data is None:
            logger.warning("outreach_json_failed_using_fallback", company=company)
            return OutreachMessages(
                linkedin_note=f"Interested in the {hypothesis_role} opportunity at {company}. Would love to connect.",
                cold_email=f"Subject: {hypothesis_role} opportunity at {company}\n\nI noticed {company}'s recent growth and believe my experience aligns well. Would you be open to a brief conversation?",
                follow_up=f"Following up on my note about the {hypothesis_role} role at {company}. Happy to share more context on my background.",
            )
        return OutreachMessages(**data)

    def generate_full_pack(
        self,
        company: str,
        signal_type: str,
        signal_context: str,
        likely_roles: list[str],
        profile_summary: str,
        tone: str = "confident",
    ) -> ShadowPack:
        """
        Generate complete Shadow Application Pack.

        Runs sequentially: hypothesis → memo → outreach.
        CV tailoring is handled separately by the Celery task via the
        existing edit_plan → render_docx pipeline.

        If profile_summary is thin, we add a note telling Claude to
        work with what's available rather than refusing.
        """
        # Step 1: Hiring hypothesis
        # Pad thin profiles so Claude doesn't refuse
        if not profile_summary or len(profile_summary.strip()) < 50:
            profile_summary = (
                f"Senior professional exploring opportunities.\n"
                f"Target company: {company}\n"
                f"Signal context: {signal_context}\n"
                f"Note: candidate profile is minimal — generate the best possible "
                f"output with available information. Do not refuse or ask for more data."
            )

        hypothesis = self.generate_hypothesis(
            company=company,
            signal_type=signal_type,
            signal_context=signal_context,
            likely_roles=likely_roles,
            profile_summary=profile_summary,
        )

        hypothesis_role = hypothesis.get("hypothesis_role", likely_roles[0] if likely_roles else "Senior Role")
        hiring_hypothesis = hypothesis.get("hiring_hypothesis", "")
        confidence = hypothesis.get("confidence", 0.5)
        reasoning = hypothesis.get("reasoning", "")

        # Post-LLM confidence cap based on input quality
        # Claude often returns high confidence regardless — we enforce reality
        confidence = _cap_confidence(company, signal_context, confidence)

        # Step 2: Strategy memo
        strategy_memo = self.generate_strategy_memo(
            company=company,
            hiring_hypothesis=hiring_hypothesis,
            profile_summary=profile_summary,
            signal_context=signal_context,
        )

        # Step 3: Outreach messages
        outreach = self.generate_outreach(
            company=company,
            hypothesis_role=hypothesis_role,
            hiring_hypothesis=hiring_hypothesis,
            strategy_memo=strategy_memo,
            profile_summary=profile_summary,
            tone=tone,
        )

        return ShadowPack(
            hypothesis_role=hypothesis_role,
            hiring_hypothesis=hiring_hypothesis,
            strategy_memo=strategy_memo,
            outreach=outreach,
            confidence=confidence,
            reasoning=reasoning,
        )
