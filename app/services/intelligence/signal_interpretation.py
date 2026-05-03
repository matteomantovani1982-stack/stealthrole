"""
app/services/intelligence/signal_interpretation.py

Signal Interpretation Layer — Phase 3 of Signal Intelligence Layer.

Transforms raw HiddenSignal records into structured business
interpretations via a versioned rule engine.  Each rule maps a
(trigger_type, keyword pattern) to:

  * business_change — what is happening to the business
  * org_impact      — what org changes this implies
  * hiring_reason   — why specific roles will be created
  * predicted_roles — [{role, seniority, confidence, timeline, urgency}]
  * hiring_owner    — who will own the hiring decision

Rules are matched against the signal's headline, reasoning, and
signal_data using keyword overlap.  The best-matching rule wins.
An ``interpretation_confidence`` (0.0–1.0) is assigned based on the
ratio of matched keywords to total rule keywords.

Only signals that passed the quality gate (``pass`` or
``conditional``) should be interpreted.

Usage
-----
    from app.services.intelligence.signal_interpretation import (
        SignalInterpretationEngine,
    )

    engine = SignalInterpretationEngine(db)
    interp = await engine.interpret(signal, user_id)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.hidden_signal import HiddenSignal
    from app.models.signal_interpretation import SignalInterpretation

logger = structlog.get_logger(__name__)


# =====================================================================
# Rule definitions
# =====================================================================

@dataclass(frozen=True, slots=True)
class PredictedRole:
    """A single predicted role produced by a rule."""

    role: str
    seniority: str  # ic | manager | senior_manager | director | vp | c_suite
    confidence: float  # 0.0–1.0
    timeline: str  # immediate | 1_3_months | 3_6_months | 6_12_months
    urgency: str  # imminent | likely | possible


@dataclass(frozen=True, slots=True)
class InterpretationRule:
    """Versioned rule mapping signal patterns to business analysis."""

    rule_id: str
    version: int
    trigger_type: str
    trigger_subtype: str | None
    keywords: tuple[str, ...]
    min_keywords: int
    business_change: str
    org_impact: str
    hiring_reason: str
    predicted_roles: tuple[PredictedRole, ...]
    hiring_owner_title: str
    hiring_owner_dept: str
    # Optional: signal types this rule applies to (empty = any)
    signal_types: tuple[str, ...] = ()


# ── Funding rules ────────────────────────────────────────────────────

_FUND_SEED_A = InterpretationRule(
    rule_id="FUND_SEED_A",
    version=1,
    trigger_type="funding",
    trigger_subtype="seed_series_a",
    keywords=(
        "seed", "series a", "pre-seed", "angel",
        "raised", "funding", "million",
    ),
    min_keywords=2,
    business_change=(
        "Company secured early-stage funding and will "
        "build its core team to achieve product-market fit."
    ),
    org_impact=(
        "Founding team needs operational and "
        "technical hires to move from prototype to scale."
    ),
    hiring_reason=(
        "Post-seed/A companies must convert capital into "
        "execution capacity within 12-18 months."
    ),
    predicted_roles=(
        PredictedRole(
            "Head of Operations", "director", 0.75,
            "1_3_months", "imminent",
        ),
        PredictedRole(
            "VP Engineering", "vp", 0.60,
            "1_3_months", "likely",
        ),
    ),
    hiring_owner_title="CEO / Founder",
    hiring_owner_dept="executive",
    signal_types=("funding",),
)

_FUND_SERIES_B = InterpretationRule(
    rule_id="FUND_SERIES_B",
    version=1,
    trigger_type="funding",
    trigger_subtype="series_b",
    keywords=(
        "series b", "growth round", "growth capital",
        "scale", "expansion", "raised", "million",
    ),
    min_keywords=2,
    business_change=(
        "Company completed growth-stage funding and must "
        "professionalise operations for rapid scaling."
    ),
    org_impact=(
        "Board pressure to add C-level / VP operational "
        "leadership within 90 days of close."
    ),
    hiring_reason=(
        "Series B is the inflection point where startups "
        "hire their first COO or VP Operations."
    ),
    predicted_roles=(
        PredictedRole(
            "VP Operations / COO", "vp", 0.80,
            "1_3_months", "imminent",
        ),
        PredictedRole(
            "CFO", "c_suite", 0.55,
            "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="CEO",
    hiring_owner_dept="executive",
    signal_types=("funding",),
)

_FUND_SERIES_C = InterpretationRule(
    rule_id="FUND_SERIES_C",
    version=1,
    trigger_type="funding",
    trigger_subtype="series_c_plus",
    keywords=(
        "series c", "series d", "series e",
        "late stage", "late-stage", "mega round",
        "hundred million", "billion",
    ),
    min_keywords=1,
    business_change=(
        "Late-stage funding signals pre-IPO preparation "
        "or international expansion at scale."
    ),
    org_impact=(
        "Company needs governance, compliance, and "
        "regional leadership for global operations."
    ),
    hiring_reason=(
        "Pre-IPO and late-stage companies add CFOs, "
        "CLOs, and regional directors."
    ),
    predicted_roles=(
        PredictedRole(
            "CFO", "c_suite", 0.70,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "General Counsel", "c_suite", 0.55,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "Regional Director", "director", 0.60,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="CEO / Board",
    hiring_owner_dept="executive",
    signal_types=("funding",),
)

_FUND_PE = InterpretationRule(
    rule_id="FUND_PE",
    version=1,
    trigger_type="funding",
    trigger_subtype="pe_investment",
    keywords=(
        "private equity", "pe firm", "buyout",
        "portfolio", "operational improvement",
        "leveraged", "lbo",
    ),
    min_keywords=2,
    business_change=(
        "PE acquisition triggers a value-creation plan "
        "with new operational leadership."
    ),
    org_impact=(
        "PE firms install operating partners or "
        "portfolio COOs within 90 days of close."
    ),
    hiring_reason=(
        "PE playbook requires dedicated operational "
        "leadership to execute the 100-day plan."
    ),
    predicted_roles=(
        PredictedRole(
            "Operating Partner", "vp", 0.80,
            "1_3_months", "imminent",
        ),
        PredictedRole(
            "Portfolio COO", "c_suite", 0.65,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="PE Managing Partner",
    hiring_owner_dept="executive",
    signal_types=("funding",),
)

# ── Leadership rules ─────────────────────────────────────────────────

_LEAD_CEO_DEPART = InterpretationRule(
    rule_id="LEAD_CEO_DEPART",
    version=1,
    trigger_type="leadership",
    trigger_subtype="ceo_departure",
    keywords=(
        "ceo", "chief executive", "steps down",
        "resigns", "departed", "leaves", "exit",
    ),
    min_keywords=2,
    business_change=(
        "CEO departure creates a leadership vacuum "
        "requiring an urgent replacement search."
    ),
    org_impact=(
        "Board launches executive search; interim "
        "leader appointed while search runs."
    ),
    hiring_reason=(
        "CEO replacement is the highest-urgency hire "
        "a board can make."
    ),
    predicted_roles=(
        PredictedRole(
            "CEO", "c_suite", 0.85,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="Board Chair",
    hiring_owner_dept="board",
    signal_types=("leadership",),
)

_LEAD_CXO_APPOINT = InterpretationRule(
    rule_id="LEAD_CXO_APPOINT",
    version=1,
    trigger_type="leadership",
    trigger_subtype="cxo_appointment",
    keywords=(
        "appoints", "appointed", "names", "joins as",
        "promoted", "new coo", "new cfo", "new cto",
        "chief", "officer",
    ),
    min_keywords=2,
    business_change=(
        "New C-suite appointment signals strategic "
        "shift and team restructuring below."
    ),
    org_impact=(
        "New CxO typically rebuilds direct-report "
        "layer within first 6 months."
    ),
    hiring_reason=(
        "Incoming executives bring their own "
        "lieutenants or restructure the team."
    ),
    predicted_roles=(
        PredictedRole(
            "VP / Director (under new CxO)", "vp", 0.70,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "Chief of Staff", "director", 0.50,
            "1_3_months", "likely",
        ),
    ),
    hiring_owner_title="Newly appointed CxO",
    hiring_owner_dept="varies",
    signal_types=("leadership",),
)

_LEAD_VP_DIRECTOR = InterpretationRule(
    rule_id="LEAD_VP_DIRECTOR",
    version=1,
    trigger_type="leadership",
    trigger_subtype="vp_director_change",
    keywords=(
        "vice president", "vp of", "director of",
        "head of", "managing director",
        "country manager", "general manager",
    ),
    min_keywords=1,
    business_change=(
        "VP / Director level change indicates "
        "functional team restructuring."
    ),
    org_impact=(
        "Backfill needed plus potential team "
        "re-alignment under new leader."
    ),
    hiring_reason=(
        "Senior-manager-level vacancy plus "
        "downstream team rebuilding."
    ),
    predicted_roles=(
        PredictedRole(
            "Senior Manager / Director", "director", 0.65,
            "1_3_months", "likely",
        ),
    ),
    hiring_owner_title="CxO / SVP",
    hiring_owner_dept="varies",
    signal_types=("leadership",),
)

# ── Expansion rules ──────────────────────────────────────────────────

_EXPAND_NEW_MARKET = InterpretationRule(
    rule_id="EXPAND_NEW_MARKET",
    version=1,
    trigger_type="expansion",
    trigger_subtype="new_market",
    keywords=(
        "expands", "expansion", "enters", "new market",
        "launches in", "new office", "opens office",
    ),
    min_keywords=1,
    business_change=(
        "Company is entering a new geography requiring "
        "local leadership and team."
    ),
    org_impact=(
        "First hire in new market is typically a "
        "country manager or regional director."
    ),
    hiring_reason=(
        "Market entry requires on-the-ground "
        "leadership for regulatory and commercial setup."
    ),
    predicted_roles=(
        PredictedRole(
            "Country Manager", "director", 0.80,
            "1_3_months", "imminent",
        ),
        PredictedRole(
            "Regional Director", "director", 0.65,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="COO / CEO",
    hiring_owner_dept="operations",
    signal_types=("expansion",),
)

_EXPAND_PRODUCT = InterpretationRule(
    rule_id="EXPAND_PRODUCT",
    version=1,
    trigger_type="expansion",
    trigger_subtype="product_launch",
    keywords=(
        "new product", "product launch", "launches",
        "unveils", "introduces", "new platform",
        "new service",
    ),
    min_keywords=1,
    business_change=(
        "New product line requires dedicated "
        "product and engineering leadership."
    ),
    org_impact=(
        "Product org expands with new PM, "
        "engineering, and go-to-market hires."
    ),
    hiring_reason=(
        "Product launches create immediate demand "
        "for product leaders and GTM teams."
    ),
    predicted_roles=(
        PredictedRole(
            "Head of Product", "director", 0.70,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "VP Engineering", "vp", 0.55,
            "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="CPO / CEO",
    hiring_owner_dept="product",
    signal_types=("expansion", "product_launch"),
)

# ── M&A rules ────────────────────────────────────────────────────────

_MA_ACQUISITION = InterpretationRule(
    rule_id="MA_ACQUISITION",
    version=1,
    trigger_type="competitive",
    trigger_subtype="acquisition",
    keywords=(
        "acquisition", "acquired", "acquires",
        "merger", "takeover", "buy-out", "buyout",
    ),
    min_keywords=1,
    business_change=(
        "Post-acquisition integration requires "
        "dedicated operational leadership."
    ),
    org_impact=(
        "Integration team formed; duplicate roles "
        "consolidated; new leadership needed."
    ),
    hiring_reason=(
        "M&A creates integration-lead and "
        "combined-entity COO demand."
    ),
    predicted_roles=(
        PredictedRole(
            "Integration Lead", "director", 0.75,
            "1_3_months", "imminent",
        ),
        PredictedRole(
            "COO (combined entity)", "c_suite", 0.60,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="CEO / PE Partner",
    hiring_owner_dept="executive",
    signal_types=("ma_activity",),
)

# ── Board / governance rules ─────────────────────────────────────────

_BOARD_CHANGE = InterpretationRule(
    rule_id="BOARD_CHANGE",
    version=1,
    trigger_type="lifecycle",
    trigger_subtype="board_change",
    keywords=(
        "board of directors", "board member",
        "board seat", "joins board", "new chairman",
        "advisory board",
    ),
    min_keywords=1,
    business_change=(
        "Board-level change signals strategic "
        "direction shift or governance upgrade."
    ),
    org_impact=(
        "New board members often push for "
        "executive-level changes within 6 months."
    ),
    hiring_reason=(
        "Board-driven mandate for new leadership "
        "to execute revised strategy."
    ),
    predicted_roles=(
        PredictedRole(
            "C-suite (board-driven)", "c_suite", 0.55,
            "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="Board Chair",
    hiring_owner_dept="board",
    signal_types=("board_change",),
)

# ── Regulatory rules ─────────────────────────────────────────────────

_REG_COMPLIANCE = InterpretationRule(
    rule_id="REG_COMPLIANCE",
    version=1,
    trigger_type="regulatory",
    trigger_subtype="compliance_mandate",
    keywords=(
        "regulation", "compliance", "new rules",
        "mandatory", "regulatory fine", "regulatory change",
        "compliance requirement",
    ),
    min_keywords=2,
    business_change=(
        "New regulation forces companies to build "
        "or expand compliance function."
    ),
    org_impact=(
        "Compliance team headcount grows; may need "
        "dedicated Head of Compliance or GRC lead."
    ),
    hiring_reason=(
        "Regulatory deadlines create non-negotiable "
        "hiring timelines."
    ),
    predicted_roles=(
        PredictedRole(
            "Head of Compliance / GRC Lead", "director",
            0.70, "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="General Counsel / CEO",
    hiring_owner_dept="legal",
    signal_types=("structural",),
)

_REG_DATA_PRIVACY = InterpretationRule(
    rule_id="REG_DATA_PRIVACY",
    version=1,
    trigger_type="regulatory",
    trigger_subtype="data_privacy",
    keywords=(
        "data protection", "privacy", "gdpr",
        "data law", "data breach", "security breach",
    ),
    min_keywords=1,
    business_change=(
        "Data privacy regulation or breach forces "
        "appointment of a Data Protection Officer."
    ),
    org_impact=(
        "DPO role created or elevated to "
        "board-reporting level."
    ),
    hiring_reason=(
        "Regulatory mandate requires a named DPO; "
        "breach accelerates the timeline."
    ),
    predicted_roles=(
        PredictedRole(
            "Data Protection Officer", "director", 0.75,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="CTO / General Counsel",
    hiring_owner_dept="legal",
    signal_types=("structural", "pain_signal"),
)

# ── Distress / turnaround rules ──────────────────────────────────────

_DISTRESS_TURNAROUND = InterpretationRule(
    rule_id="DISTRESS_TURNAROUND",
    version=1,
    trigger_type="lifecycle",
    trigger_subtype="turnaround",
    keywords=(
        "turnaround", "restructuring", "restructure",
        "transformation", "new leadership",
        "cost optimization",
    ),
    min_keywords=1,
    business_change=(
        "Company in distress requires turnaround "
        "leadership to stabilise operations."
    ),
    org_impact=(
        "Existing leadership replaced; board "
        "appoints transformation team."
    ),
    hiring_reason=(
        "Turnaround situations create urgent "
        "C-suite and operational leadership demand."
    ),
    predicted_roles=(
        PredictedRole(
            "Transformation Lead / COO", "c_suite",
            0.75, "1_3_months", "imminent",
        ),
        PredictedRole(
            "Interim CFO", "c_suite", 0.55,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="Board / PE Partner",
    hiring_owner_dept="board",
    signal_types=("distress",),
)

# ── Pain signal rules ────────────────────────────────────────────────

_PAIN_TALENT = InterpretationRule(
    rule_id="PAIN_TALENT",
    version=1,
    trigger_type="competitive",
    trigger_subtype="talent_pain",
    keywords=(
        "turnover", "employee reviews", "glassdoor",
        "workplace culture", "toxic", "burnout",
        "key departure",
    ),
    min_keywords=2,
    business_change=(
        "Talent crisis (high turnover / culture "
        "issues) forces leadership intervention."
    ),
    org_impact=(
        "Chief People Officer or VP People "
        "hired to stabilise retention."
    ),
    hiring_reason=(
        "Visible culture problems trigger board "
        "or investor demand for people leadership."
    ),
    predicted_roles=(
        PredictedRole(
            "Chief People Officer / VP HR",
            "vp", 0.65, "1_3_months", "likely",
        ),
    ),
    hiring_owner_title="CEO",
    hiring_owner_dept="executive",
    signal_types=("pain_signal",),
)

# ── Structural rules ────────────────────────────────────────────────

_STRUCT_SPINOFF = InterpretationRule(
    rule_id="STRUCT_SPINOFF",
    version=1,
    trigger_type="lifecycle",
    trigger_subtype="spinoff",
    keywords=(
        "spin-off", "carve-out", "demerger",
        "strategic pivot", "pivot to", "rebrand",
    ),
    min_keywords=1,
    business_change=(
        "Corporate restructuring (spin-off or pivot) "
        "creates a standalone entity needing full C-suite."
    ),
    org_impact=(
        "New entity requires CEO, CFO, COO, and "
        "functional leadership from scratch."
    ),
    hiring_reason=(
        "Spin-offs must staff entire leadership "
        "team within 6-12 months."
    ),
    predicted_roles=(
        PredictedRole(
            "CEO (spin-off)", "c_suite", 0.65,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "CFO (spin-off)", "c_suite", 0.55,
            "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="Parent company Board",
    hiring_owner_dept="board",
    signal_types=("structural",),
)

_STRUCT_DIGITAL_TX = InterpretationRule(
    rule_id="STRUCT_DIGITAL_TX",
    version=1,
    trigger_type="technology",
    trigger_subtype="digital_transformation",
    keywords=(
        "digital transformation", "ai adoption",
        "automation", "technology investment",
        "modernization", "modernisation",
    ),
    min_keywords=1,
    business_change=(
        "Digital transformation initiative "
        "requires senior technology leadership."
    ),
    org_impact=(
        "CTO / VP Eng / CDO hired to drive "
        "multi-year transformation programme."
    ),
    hiring_reason=(
        "Transformation programmes need a senior "
        "technologist with executive presence."
    ),
    predicted_roles=(
        PredictedRole(
            "CTO / VP Engineering", "c_suite", 0.70,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "Chief Digital Officer", "c_suite", 0.55,
            "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="CEO / Board",
    hiring_owner_dept="executive",
    signal_types=("structural",),
)

# ── Market signal rules ──────────────────────────────────────────────

_MARKET_COMPETITOR = InterpretationRule(
    rule_id="MARKET_COMPETITOR",
    version=1,
    trigger_type="competitive",
    trigger_subtype="competitor_funding",
    keywords=(
        "competitor raised", "competitor funding",
        "market share", "competitive response",
        "talent war", "poaching",
    ),
    min_keywords=1,
    business_change=(
        "Competitor activity forces defensive "
        "hiring to protect market position."
    ),
    org_impact=(
        "VP Sales / Head of Growth hired to "
        "counter competitive threat."
    ),
    hiring_reason=(
        "Revenue defense is the top priority "
        "when competitors scale up."
    ),
    predicted_roles=(
        PredictedRole(
            "VP Sales / Head of Growth", "vp",
            0.65, "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="CEO / CRO",
    hiring_owner_dept="commercial",
    signal_types=("market_signal",),
)

_MARKET_GOVT_CONTRACT = InterpretationRule(
    rule_id="MARKET_GOVT_CONTRACT",
    version=1,
    trigger_type="expansion",
    trigger_subtype="government_contract",
    keywords=(
        "government contract", "awarded contract",
        "enterprise contract", "government policy",
    ),
    min_keywords=1,
    business_change=(
        "Major contract win requires delivery "
        "team scale-up to meet SLA commitments."
    ),
    org_impact=(
        "Delivery / program management leadership "
        "added to run the new engagement."
    ),
    hiring_reason=(
        "Contract SLAs have hard deadlines — "
        "team must be in place before start date."
    ),
    predicted_roles=(
        PredictedRole(
            "Program Director", "director", 0.70,
            "1_3_months", "imminent",
        ),
        PredictedRole(
            "Head of Delivery", "director", 0.60,
            "1_3_months", "imminent",
        ),
    ),
    hiring_owner_title="COO / CEO",
    hiring_owner_dept="operations",
    signal_types=("market_signal",),
)

# ── Hiring surge rule ────────────────────────────────────────────────

_HIRING_SURGE = InterpretationRule(
    rule_id="HIRING_SURGE",
    version=1,
    trigger_type="expansion",
    trigger_subtype="hiring_surge",
    keywords=(
        "hiring", "recruiting", "open positions",
        "job postings", "hiring spree",
        "talent acquisition",
    ),
    min_keywords=1,
    business_change=(
        "Company shows elevated posting volume "
        "indicating active team build-out."
    ),
    org_impact=(
        "Multiple simultaneous vacancies suggest "
        "a new function or rapid scaling."
    ),
    hiring_reason=(
        "Hiring surge is a leading indicator of "
        "budget approval for team expansion."
    ),
    predicted_roles=(
        PredictedRole(
            "Senior Manager / Director (multiple)",
            "director", 0.60, "1_3_months", "likely",
        ),
    ),
    hiring_owner_title="VP / CxO (function TBD)",
    hiring_owner_dept="varies",
    signal_types=("hiring_surge", "velocity"),
)

# ── IPO rule ─────────────────────────────────────────────────────────

_LIFECYCLE_IPO = InterpretationRule(
    rule_id="LIFECYCLE_IPO",
    version=1,
    trigger_type="lifecycle",
    trigger_subtype="ipo_preparation",
    keywords=(
        "ipo", "public", "listing", "pre-ipo",
        "going public",
    ),
    min_keywords=1,
    business_change=(
        "IPO preparation requires governance, "
        "compliance, and IR infrastructure."
    ),
    org_impact=(
        "CFO, CLO, Head of IR, and compliance "
        "team must be in place 12+ months before listing."
    ),
    hiring_reason=(
        "Regulatory requirements mandate specific "
        "governance roles before listing."
    ),
    predicted_roles=(
        PredictedRole(
            "CFO", "c_suite", 0.80,
            "3_6_months", "likely",
        ),
        PredictedRole(
            "Chief Compliance Officer", "c_suite",
            0.65, "3_6_months", "likely",
        ),
        PredictedRole(
            "Head of Investor Relations", "director",
            0.60, "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="CEO / Board",
    hiring_owner_dept="executive",
    signal_types=("funding",),
)

# ── ESG rule ─────────────────────────────────────────────────────────

_STRUCT_ESG = InterpretationRule(
    rule_id="STRUCT_ESG",
    version=1,
    trigger_type="regulatory",
    trigger_subtype="esg_mandate",
    keywords=(
        "esg", "sustainability", "esg commitment",
        "sustainability initiative", "carbon",
        "net zero",
    ),
    min_keywords=1,
    business_change=(
        "ESG mandate or commitment requires "
        "dedicated sustainability leadership."
    ),
    org_impact=(
        "Chief Sustainability Officer or Head of "
        "ESG created as a new function."
    ),
    hiring_reason=(
        "Investor and regulatory pressure makes "
        "ESG leadership a board-level priority."
    ),
    predicted_roles=(
        PredictedRole(
            "Chief Sustainability Officer", "c_suite",
            0.60, "3_6_months", "likely",
        ),
    ),
    hiring_owner_title="CEO / Board",
    hiring_owner_dept="executive",
    signal_types=("structural",),
)


# ── Master rule registry ─────────────────────────────────────────────

RULES: tuple[InterpretationRule, ...] = (
    _FUND_SEED_A,
    _FUND_SERIES_B,
    _FUND_SERIES_C,
    _FUND_PE,
    _LEAD_CEO_DEPART,
    _LEAD_CXO_APPOINT,
    _LEAD_VP_DIRECTOR,
    _EXPAND_NEW_MARKET,
    _EXPAND_PRODUCT,
    _MA_ACQUISITION,
    _BOARD_CHANGE,
    _REG_COMPLIANCE,
    _REG_DATA_PRIVACY,
    _DISTRESS_TURNAROUND,
    _PAIN_TALENT,
    _STRUCT_SPINOFF,
    _STRUCT_DIGITAL_TX,
    _MARKET_COMPETITOR,
    _MARKET_GOVT_CONTRACT,
    _HIRING_SURGE,
    _LIFECYCLE_IPO,
    _STRUCT_ESG,
)


# =====================================================================
# Engine
# =====================================================================

class SignalInterpretationEngine:
    """Match signals against rules and produce interpretations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Public API ───────────────────────────────────────────────────

    async def interpret(
        self,
        signal: HiddenSignal,
        user_id: str,
    ) -> SignalInterpretation | None:
        """Interpret a single signal. Returns ``None`` when no rule
        matches or the signal should not be interpreted (wrong gate).

        The caller owns ``db.commit()``.
        """
        # Only interpret pass / conditional signals
        gate = signal.quality_gate_result
        if gate and gate not in ("pass", "conditional"):
            return None

        match = self._match(signal)
        if match is None:
            logger.debug(
                "interpretation_no_match",
                signal_id=str(signal.id),
                signal_type=signal.signal_type,
            )
            return None

        rule, confidence = match
        interp = self._build_record(signal, user_id, rule, confidence)
        self._db.add(interp)

        logger.info(
            "signal_interpreted",
            signal_id=str(signal.id),
            rule_id=rule.rule_id,
            confidence=round(confidence, 2),
            roles=len(rule.predicted_roles),
        )
        return interp

    async def interpret_batch(
        self,
        signals: list[HiddenSignal],
        user_id: str,
    ) -> list[SignalInterpretation]:
        """Interpret a list of signals. Returns created records."""
        results: list[SignalInterpretation] = []
        for sig in signals:
            interp = await self.interpret(sig, user_id)
            if interp is not None:
                results.append(interp)
        return results

    # ── Rule matching ────────────────────────────────────────────────

    def _match(
        self,
        signal: HiddenSignal,
    ) -> tuple[InterpretationRule, float] | None:
        """Find the best-matching rule for a signal.

        Returns ``(rule, interpretation_confidence)`` or ``None``.
        """
        text = self._signal_text(signal)
        sig_type = signal.signal_type or ""

        best_rule: InterpretationRule | None = None
        best_score = 0.0

        for rule in RULES:
            # Filter by signal type if the rule constrains it
            if rule.signal_types and sig_type not in rule.signal_types:
                continue

            hits = sum(
                1 for kw in rule.keywords if kw in text
            )
            if hits < rule.min_keywords:
                continue

            # Overlap ratio = matched / total keywords
            ratio = hits / len(rule.keywords)

            if ratio > best_score:
                best_score = ratio
                best_rule = rule

        if best_rule is None:
            return None

        # Clamp confidence to [0.20, 0.95]
        confidence = max(0.20, min(0.95, best_score))
        return best_rule, confidence

    @staticmethod
    def _signal_text(signal: HiddenSignal) -> str:
        """Build searchable text corpus from the signal."""
        parts = [
            signal.company_name or "",
            signal.signal_type or "",
            signal.reasoning or "",
        ]
        data = signal.signal_data or {}
        for key in (
            "funding_round_type", "person_title",
            "sector", "location",
        ):
            val = data.get(key)
            if val:
                parts.append(str(val))

        # Include likely_roles text
        for role in signal.likely_roles or []:
            if isinstance(role, str):
                parts.append(role)
            elif isinstance(role, dict):
                parts.append(str(role.get("role", "")))

        return " ".join(parts).lower()

    # ── Record builder ───────────────────────────────────────────────

    @staticmethod
    def _build_record(
        signal: HiddenSignal,
        user_id: str,
        rule: InterpretationRule,
        confidence: float,
    ) -> SignalInterpretation:
        """Create a SignalInterpretation ORM instance."""
        from app.models.signal_interpretation import (
            SignalInterpretation as SIModel,
        )

        roles_json = [
            {
                "role": pr.role,
                "seniority": pr.seniority,
                "confidence": pr.confidence,
                "timeline": pr.timeline,
                "urgency": pr.urgency,
            }
            for pr in rule.predicted_roles
        ]

        return SIModel(
            signal_id=signal.id,
            user_id=user_id,
            rule_id=rule.rule_id,
            rule_version=rule.version,
            trigger_type=rule.trigger_type,
            trigger_subtype=rule.trigger_subtype,
            business_change=rule.business_change,
            org_impact=rule.org_impact,
            hiring_reason=rule.hiring_reason,
            predicted_roles=roles_json,
            hiring_owner_title=rule.hiring_owner_title,
            hiring_owner_dept=rule.hiring_owner_dept,
            quality_score=signal.quality_score,
            interpretation_confidence=confidence,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
