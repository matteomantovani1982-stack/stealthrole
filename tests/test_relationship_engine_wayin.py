"""
tests/test_relationship_engine_wayin.py

Way In pipeline coverage. These tests pin down the contract the user laid out:

- never return synthetic stub names ("Recruiter — <company>")
- 1st degree → direct message
- 2nd degree → real connector path + intro request
- unlabeled (no verified 1st/2nd) → target only, no fake connector, no auto message
- recruiters / hiring authority outrank random IC's at the same company
- VP/Director classifies as VP_DIRECTOR (not C_SUITE)
- candidates whose company clearly doesn't match get rejected
- empty candidate name is dropped
- pipeline returns [] when discovery fails (no synthetic fallback)

We test the pure pipeline stages directly with no DB / network / LLM. The
async stages that touch the DB (`_wayin_overlay_network`) and LLM
(`_wayin_finalize` → `_craft_message`) are covered with light monkeypatching.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.linkedin import relationship_engine as re_mod
from app.services.linkedin.relationship_engine import (
    RelationshipEngine,
    companies_match,
    detect_domain,
    normalize_company,
    normalize_text,
    seniority_tier,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _engine() -> RelationshipEngine:
    """RelationshipEngine with a no-op DB. Pure stages don't touch it."""
    db = MagicMock()
    db.execute = AsyncMock()
    return RelationshipEngine(db=db)


def _make_conn(
    full_name: str,
    *,
    company: str | None = None,
    title: str | None = None,
    url: str | None = None,
    linkedin_id: str | None = None,
    relationship_strength: str | None = "medium",
    user_id: str = "u-1",
) -> SimpleNamespace:
    """Lightweight LinkedInConnection stand-in (only fields the pipeline reads)."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name=full_name,
        current_company=company,
        current_title=title,
        headline=title or "",
        linkedin_url=url,
        linkedin_id=linkedin_id,
        relationship_strength=relationship_strength,
    )


def _serper_item(
    name: str, title: str, company_hint: str | None = None,
    snippet: str = "", url: str | None = None,
) -> dict:
    """Build a Serper organic result the way Google returns them."""
    title_field = " - ".join(
        p for p in [name, title, (f"{company_hint} | LinkedIn" if company_hint else "LinkedIn")] if p
    )
    return {
        "title": title_field,
        "snippet": snippet,
        "link": url or f"https://www.linkedin.com/in/{name.lower().replace(' ', '-')}",
    }


# ── normalization + matching ─────────────────────────────────────────────────


class TestNormalization:
    def test_normalize_text_strips_punctuation_and_lowercases(self):
        assert normalize_text("Mashreq Bank, P.S.C.") == "mashreq bank p s c"

    def test_normalize_text_handles_empty(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""  # type: ignore[arg-type]

    def test_normalize_company_strips_suffixes_and_aliases(self):
        assert normalize_company("Mashreq Bank PSC") == "mashreq bank"
        assert normalize_company("Mashreq Neo") == "mashreq bank"
        assert normalize_company("Amazon Web Services") == "amazon"


class TestCompaniesMatch:
    def test_mashreq_aliases_match(self):
        assert companies_match("Mashreq", "Mashreq Bank")
        assert companies_match("Mashreq Neo", "Mashreq Bank PSC")

    def test_short_substring_does_not_false_positive(self):
        # "bank" inside "Mashreq Bank" must NOT match "Bank of America"
        assert not companies_match("Bank of America", "Mashreq Bank")

    def test_generic_first_word_blocked(self):
        # "Digital Zone" vs "Digital Banking" was producing the Revolut bug
        assert not companies_match("Digital Zone", "Digital Banking Expansion")


# ── seniority classification ─────────────────────────────────────────────────


class TestSeniorityTier:
    def test_recruiter_is_tier_zero(self):
        assert seniority_tier("Senior Talent Acquisition Partner") == (0, "RECRUITER")
        assert seniority_tier("Recruitment Lead")[1] == "RECRUITER"

    def test_vp_is_vp_director_not_c_suite(self):
        # Critical: "Vice President" contains "president" — must classify as
        # VP_DIRECTOR, not C_SUITE.
        assert seniority_tier("Vice President of Engineering") == (3, "VP_DIRECTOR")
        assert seniority_tier("VP Marketing")[1] == "VP_DIRECTOR"
        assert seniority_tier("Director of Strategy")[1] == "VP_DIRECTOR"
        assert seniority_tier("Head of Talent")[1] == "VP_DIRECTOR"

    def test_managing_director_and_chief_are_csuite(self):
        assert seniority_tier("Managing Director")[1] == "C_SUITE"
        assert seniority_tier("Chief Operating Officer")[1] == "C_SUITE"
        assert seniority_tier("Founder & CEO")[1] == "C_SUITE"

    def test_manager_and_ic(self):
        assert seniority_tier("Senior Manager")[1] == "MANAGER"
        assert seniority_tier("Software Engineer")[1] == "IC"


# ── tokens ───────────────────────────────────────────────────────────────────


class TestTokenization:
    def test_generic_company_words_are_filtered(self):
        eng = _engine()
        company_tokens, _, _ = eng._wayin_tokens("Bank of Mashreq", "VP Strategy")
        # "bank" is generic → must be dropped, but "mashreq" must survive.
        assert "mashreq" in company_tokens
        assert "bank" not in company_tokens

    def test_region_tokens_detect_uae_and_mena(self):
        eng = _engine()
        _, _, region = eng._wayin_tokens("Mashreq Bank", "VP Strategy MENA UAE")
        assert "mena" in region
        assert "uae" in region


# ── parse + normalize stages ─────────────────────────────────────────────────


class TestParseSerperItem:
    def test_extracts_name_title_and_company_hint(self):
        eng = _engine()
        item = _serper_item(
            "Sarah Ahmed", "Head of Talent Acquisition", company_hint="Mashreq Bank",
            url="https://www.linkedin.com/in/sarah-ahmed",
        )
        rec = eng._wayin_parse_serper_item(item, source_query="q")
        assert rec is not None
        assert rec["name"] == "Sarah Ahmed"
        assert rec["title"] == "Head of Talent Acquisition"
        assert rec["company_hint"] == "Mashreq Bank"
        assert rec["linkedin_url"] == "https://www.linkedin.com/in/sarah-ahmed"

    def test_skips_non_profile_links(self):
        eng = _engine()
        rec = eng._wayin_parse_serper_item(
            {"title": "X", "link": "https://www.linkedin.com/company/mashreq", "snippet": ""},
            source_query="q",
        )
        assert rec is None

    def test_strips_linkedin_suffix_in_title(self):
        eng = _engine()
        item = {
            "title": "John Smith - Director of Engineering | LinkedIn",
            "snippet": "",
            "link": "https://www.linkedin.com/in/john-smith",
        }
        rec = eng._wayin_parse_serper_item(item, source_query="q")
        assert rec and rec["title"] == "Director of Engineering"


# ── ranking stage (the brain of Way In) ──────────────────────────────────────


class TestRanking:
    def test_recruiter_at_target_company_is_accepted_and_top_ranked(self):
        eng = _engine()
        people = [
            eng._wayin_normalize({
                "name": "Sarah Ahmed",
                "title": "Head of Talent Acquisition",
                "company_hint": "Mashreq Bank",
                "snippet": "",
                "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            }),
            eng._wayin_normalize({
                "name": "Random IC",
                "title": "Software Engineer",
                "company_hint": "Mashreq Bank",
                "snippet": "",
                "linkedin_url": "https://www.linkedin.com/in/random-ic",
            }),
        ]
        ranked = eng._wayin_rank(people, "Mashreq Bank", "VP Strategy")
        assert any(p["name"] == "Sarah Ahmed" for p in ranked)
        # IC with no hiring authority and low seniority must be filtered out.
        assert all(p["name"] != "Random IC" for p in ranked)
        assert ranked[0]["name"] == "Sarah Ahmed"
        assert ranked[0]["_is_recruiter"] is True

    def test_hiring_manager_is_accepted_and_outranks_low_signal_director(self):
        eng = _engine()
        people = [
            eng._wayin_normalize({
                "name": "Hassan Strategy",
                "title": "VP of Strategy",
                "company_hint": "Mashreq Bank",
                "snippet": "Leads strategy team at Mashreq Bank",
                "linkedin_url": "https://www.linkedin.com/in/hassan-strategy",
            }),
            eng._wayin_normalize({
                "name": "Other Director",
                "title": "Director of Compliance",
                "company_hint": "Mashreq Bank",
                "snippet": "",
                "linkedin_url": "https://www.linkedin.com/in/other-director",
            }),
        ]
        ranked = eng._wayin_rank(people, "Mashreq Bank", "VP Strategy")
        names = [p["name"] for p in ranked]
        assert "Hassan Strategy" in names
        # Strategy-function VP must outrank Compliance director for a Strategy role.
        assert names.index("Hassan Strategy") < names.index("Other Director")
        comps = ranked[0]["_rank_components"]
        assert comps["company_match"] >= 60
        assert comps["hiring"] > 0 or comps["recruiter"] > 0

    def test_company_mismatch_is_rejected(self):
        eng = _engine()
        people = [
            eng._wayin_normalize({
                "name": "Evgeny Wrong",
                "title": "VP Engineering",
                "company_hint": "Yandex",
                "snippet": "Yandex Moscow",
                "linkedin_url": "https://www.linkedin.com/in/evgeny",
            }),
        ]
        ranked = eng._wayin_rank(people, "Mashreq Bank", "VP Strategy")
        assert ranked == []

    def test_low_signal_ic_is_rejected_even_if_company_matches(self):
        eng = _engine()
        people = [
            eng._wayin_normalize({
                "name": "Junior Person",
                "title": "Analyst",
                "company_hint": "Mashreq Bank",
                "snippet": "",
                "linkedin_url": "https://www.linkedin.com/in/junior",
            }),
        ]
        assert eng._wayin_rank(people, "Mashreq Bank", "VP Strategy") == []

    def test_company_only_in_snippet_not_headline_is_rejected(self):
        """Serp snippets mention employers for talks/articles; headline must tie them to the target co."""
        eng = _engine()
        people = [
            eng._wayin_normalize({
                "name": "Consultant",
                "title": "Partner",
                "company_hint": "Accenture",
                "snippet": "Keynote on Mashreq Bank digital transformation and cloud",
                "linkedin_url": "https://www.linkedin.com/in/consultant",
            }),
        ]
        assert eng._wayin_rank(people, "Mashreq Bank", "VP Strategy") == []

    def test_former_at_target_in_snippet_without_headline_is_rejected(self):
        eng = _engine()
        people = [
            eng._wayin_normalize({
                "name": "Alumni",
                "title": "Director at Other Bank",
                "company_hint": "Other Bank",
                "snippet": "Former VP at Mashreq Bank; now at Other Bank",
                "linkedin_url": "https://www.linkedin.com/in/alumni",
            }),
        ]
        assert eng._wayin_rank(people, "Mashreq Bank", "VP Strategy") == []


# ── network overlay stage ────────────────────────────────────────────────────


class TestOverlayNetwork:
    @pytest.mark.asyncio
    async def test_first_degree_when_user_has_direct_connection(self):
        eng = _engine()
        # Empty mutuals query result.
        eng.db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))

        ranked = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent Acquisition",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn(
            "Sarah Ahmed",
            company="Mashreq Bank",
            title="Head of Talent",
            url="https://www.linkedin.com/in/sarah-ahmed",
        )]
        out = await eng._wayin_overlay_network(ranked, conns, "Mashreq Bank")
        assert out[0]["degree"] == "1st"
        assert out[0]["connection_path"] is None
        assert out[0]["_rank_score"] == 150  # +50 first-degree bonus

    @pytest.mark.asyncio
    async def test_second_degree_resolves_real_connector(self):
        eng = _engine()

        target_url = "https://www.linkedin.com/in/sarah-ahmed"
        # Mutual record: connector "Ahmed Khan" knows target "Sarah Ahmed"
        mutual = SimpleNamespace(
            target_linkedin_url=target_url,
            target_name="Sarah Ahmed",
            mutual_name="Ahmed Khan",
        )
        eng.db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: [mutual])
        ))

        ranked = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": target_url,
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn(
            "Ahmed Khan",
            company="HSBC",
            title="VP Engineering",
            url="https://www.linkedin.com/in/ahmed-khan",
        )]

        out = await eng._wayin_overlay_network(ranked, conns, "Mashreq Bank")
        assert out[0]["degree"] == "2nd"
        assert out[0]["connection_path"] is not None
        assert out[0]["connection_path"]["connector_name"] == "Ahmed Khan"
        assert out[0]["_rank_score"] == 125  # +25 second-degree bonus

    @pytest.mark.asyncio
    async def test_second_degree_matches_mutual_by_profile_slug_not_full_url(self):
        """Serper URL shape can differ from stored mutual URL; slug must still match."""
        eng = _engine()
        mutual = SimpleNamespace(
            target_linkedin_url="https://www.linkedin.com/in/sarah-ahmed",
            target_name="Sarah Ahmed",
            target_linkedin_id="ACoFAKE",
            mutual_name="Ahmed Khan",
            mutual_linkedin_id="mutual-id",
        )
        eng.db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: [mutual])
        ))
        ranked = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn(
            "Ahmed Khan",
            company="HSBC",
            title="VP",
            url="https://www.linkedin.com/in/ahmed-khan",
        )]
        out = await eng._wayin_overlay_network(ranked, conns, "Mashreq Bank")
        assert out[0]["degree"] == "2nd"
        assert out[0]["connection_path"]["connector_name"] == "Ahmed Khan"

    @pytest.mark.asyncio
    async def test_second_degree_matches_mutual_when_only_target_name_matches(self):
        eng = _engine()
        mutual = SimpleNamespace(
            target_linkedin_url=None,
            target_name="Sarah Ahmed",
            target_linkedin_id="ACoFAKE",
            mutual_name="Ahmed Khan",
            mutual_linkedin_id="x",
        )
        eng.db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: [mutual])
        ))
        ranked = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn("Ahmed Khan", url="https://www.linkedin.com/in/ahmed-khan")]
        out = await eng._wayin_overlay_network(ranked, conns, "Mashreq Bank")
        assert out[0]["degree"] == "2nd"

    @pytest.mark.asyncio
    async def test_second_degree_resolves_connector_with_credentials_on_mutual_name(self):
        eng = _engine()
        mutual = SimpleNamespace(
            target_linkedin_url="https://www.linkedin.com/in/sarah-ahmed",
            target_name="Sarah Ahmed",
            target_linkedin_id="ACoFAKE",
            mutual_name="Ahmed Khan, MBA",
            mutual_linkedin_id="y",
        )
        eng.db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: [mutual])
        ))
        ranked = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn("Ahmed Khan", url="https://www.linkedin.com/in/ahmed-khan")]
        out = await eng._wayin_overlay_network(ranked, conns, "Mashreq Bank")
        assert out[0]["degree"] == "2nd"
        assert out[0]["connection_path"]["connector_name"] == "Ahmed Khan"

    @pytest.mark.asyncio
    async def test_profile_scraped_second_degree_same_url_not_first_degree(self):
        """Extension stores 2nd-degree profile visits as relationship_strength=weak — not your 1st network."""
        eng = _engine()
        eng.db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        ranked = [{
            "name": "Nick Peel",
            "title": "Director",
            "linkedin_url": "https://www.linkedin.com/in/nick-peel-neom",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn(
            "Nick Peel",
            company="NEOM",
            title="Director",
            url="https://www.linkedin.com/in/nick-peel-neom",
            relationship_strength="weak",
        )]
        out = await eng._wayin_overlay_network(ranked, conns, "NEOM")
        assert out[0]["degree"] is None
        assert out[0]["connection_path"] is None

    @pytest.mark.asyncio
    async def test_same_display_name_different_profile_slug_is_not_first_degree(self):
        """Do not mark 1st when only name matches — URL identity must match."""
        eng = _engine()
        eng.db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        ranked = [{
            "name": "Terry John-Baptiste",
            "title": "Director of Operations",
            "linkedin_url": "https://www.linkedin.com/in/terry-john-baptiste-neom",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn(
            "Terry John-Baptiste",
            company="Other Co",
            url="https://www.linkedin.com/in/terry-john-baptiste-other",
        )]
        out = await eng._wayin_overlay_network(ranked, conns, "NEOM")
        assert out[0]["degree"] is None
        assert out[0]["connection_path"] is None

    @pytest.mark.asyncio
    async def test_second_degree_mutual_with_bidi_marks_in_stored_target_name(self):
        eng = _engine()
        # LinkedIn often wraps names in RTL/LTR marks in the DOM
        dirty = "\u200eNick Peel\u200f"
        mutual = SimpleNamespace(
            target_linkedin_url="https://www.linkedin.com/in/nick-peel-neom",
            target_name=dirty,
            target_linkedin_id="ACoFAKE",
            mutual_name="Barbara Smith",
            mutual_linkedin_id="z",
        )
        eng.db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: [mutual])
        ))
        ranked = [{
            "name": "Nick Peel",
            "title": "Director",
            "linkedin_url": "https://www.linkedin.com/in/nick-peel-neom",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn("Barbara Smith", url="https://www.linkedin.com/in/barbara-smith")]
        out = await eng._wayin_overlay_network(ranked, conns, "NEOM")
        assert out[0]["degree"] == "2nd"
        assert out[0]["connection_path"]["connector_name"] == "Barbara Smith"

    @pytest.mark.asyncio
    async def test_unlabeled_has_no_fake_connector(self):
        eng = _engine()
        eng.db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))

        ranked = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "_rank_score": 100,
            "_rank_components": {},
        }]
        conns = [_make_conn("Some Other Person", company="Wrong Co")]
        out = await eng._wayin_overlay_network(ranked, conns, "Mashreq Bank")
        assert out[0]["degree"] is None
        assert out[0]["connection_path"] is None
        assert out[0]["_rank_score"] == 100


# ── finalize stage ────────────────────────────────────────────────────────────


class TestFinalize:
    def test_unlabeled_has_no_message_no_connector(self, monkeypatch):
        eng = _engine()
        called = {"n": 0}

        def _craft(*args, **kwargs):
            called["n"] += 1
            return "FAKE_MESSAGE"
        monkeypatch.setattr(eng, "_craft_message", _craft)

        overlaid = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "degree": None,
            "connection_path": None,
            "_rank_score": 100,
            "_rank_components": {},
        }]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        assert len(out) == 1
        assert out[0]["message"] == ""
        assert out[0]["degree"] is None
        assert out[0]["connection_path"] is None
        assert called["n"] == 0

    def test_legacy_third_string_treated_as_unlabeled(self, monkeypatch):
        eng = _engine()
        called = {"n": 0}

        def _craft(**kw):
            called["n"] += 1
            return "X"

        monkeypatch.setattr(eng, "_craft_message", _craft)

        overlaid = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "degree": "3rd",
            "connection_path": None,
            "_rank_score": 100,
            "_rank_components": {},
        }]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        assert out[0]["degree"] is None
        assert out[0]["message"] == ""
        assert called["n"] == 0

    def test_first_degree_non_empty_even_if_craft_returns_blank(self, monkeypatch):
        eng = _engine()
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: "   ")
        overlaid = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "degree": "1st",
            "connection_path": None,
            "_rank_score": 150,
            "_rank_components": {},
        }]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        assert out[0]["message"].strip()
        assert "Sarah" in out[0]["message"]

    def test_second_degree_non_empty_even_if_craft_returns_blank(self, monkeypatch):
        eng = _engine()
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: "")
        overlaid = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "degree": "2nd",
            "connection_path": {
                "connector_name": "Ahmed Khan",
                "connector_title": "VP Eng",
                "connector_url": "",
                "connector_id": "x",
                "connector_headline": "Building platforms",
            },
            "_rank_score": 125,
            "_rank_components": {},
        }]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        assert out[0]["message"].strip()
        assert "Ahmed" in out[0]["message"]

    def test_first_degree_gets_direct_message(self, monkeypatch):
        eng = _engine()
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: f"DIRECT::{kw['recipient_name']}")
        overlaid = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "degree": "1st",
            "connection_path": None,
            "_rank_score": 150,
            "_rank_components": {},
        }]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        assert out[0]["message"] == "DIRECT::Sarah Ahmed"

    def test_second_degree_gets_intro_request_addressed_to_connector(self, monkeypatch):
        eng = _engine()
        captured: dict = {}

        def _craft(**kw):
            captured.update(kw)
            return f"INTRO::{kw['recipient_name']}"
        monkeypatch.setattr(eng, "_craft_message", _craft)

        overlaid = [{
            "name": "Sarah Ahmed",
            "title": "Head of Talent",
            "linkedin_url": "https://www.linkedin.com/in/sarah-ahmed",
            "snippet": "",
            "degree": "2nd",
            "connection_path": {
                "connector_name": "Ahmed Khan",
                "connector_title": "VP Eng",
                "connector_url": "",
                "connector_id": "x",
            },
            "_rank_score": 125,
            "_rank_components": {},
        }]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        assert out[0]["message"] == "INTRO::Ahmed Khan"
        assert captured["message_type"] == "intro_request"
        # Intro context must reference the actual target.
        assert "Sarah Ahmed" in captured["connector_name"]

    def test_drops_empty_target_names(self, monkeypatch):
        eng = _engine()
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: "msg")
        overlaid = [
            {"name": "  ", "title": "Head of Talent", "linkedin_url": "u",
             "snippet": "", "degree": "1st", "connection_path": None,
             "_rank_score": 1, "_rank_components": {}},
            {"name": "Real Person", "title": "VP Strategy", "linkedin_url": "u2",
             "snippet": "", "degree": "1st", "connection_path": None,
             "_rank_score": 1, "_rank_components": {}},
        ]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", "VP Strategy", "")
        names = [p["name"] for p in out]
        assert "Real Person" in names
        assert "" not in names and "  " not in names

    def test_caps_at_five(self, monkeypatch):
        eng = _engine()
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: "")
        overlaid = [
            {"name": f"P{i}", "title": "Head of Talent",
             "linkedin_url": f"u{i}", "snippet": "",
             "degree": None, "connection_path": None,
             "_rank_score": 1, "_rank_components": {}}
            for i in range(10)
        ]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", None, "")
        assert len(out) == 5

    def test_dedupes_by_name_and_url(self, monkeypatch):
        eng = _engine()
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: "")
        overlaid = [
            {"name": "Same Person", "title": "Recruiter",
             "linkedin_url": "https://x/y/", "snippet": "",
             "degree": None, "connection_path": None,
             "_rank_score": 5, "_rank_components": {}},
            {"name": "Same Person", "title": "Recruiter",
             "linkedin_url": "https://x/y", "snippet": "",
             "degree": None, "connection_path": None,
             "_rank_score": 1, "_rank_components": {}},
        ]
        out = eng._wayin_finalize(overlaid, "Mashreq Bank", None, "")
        assert len(out) == 1


# ── full _find_key_people pipeline (no synthetic stubs!) ─────────────────────


class TestFindKeyPeoplePipeline:
    @pytest.mark.asyncio
    async def test_returns_empty_when_company_undisclosed(self):
        eng = _engine()
        out = await eng._find_key_people(
            "Digital Banking Expansion (Undisclosed)", "VP Strategy", [], "",
        )
        # Honest empty — no synthetic "Recruiter — <company>" rows.
        assert out == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_serper_key(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "serper_api_key", "")
        eng = _engine()
        out = await eng._find_key_people("Mashreq Bank", "VP Strategy", [], "")
        assert out == []

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_serper(self, monkeypatch):
        """End-to-end: discovery → rank → overlay → finalize, no real I/O."""
        from app.config import settings
        monkeypatch.setattr(settings, "serper_api_key", "test-key")

        eng = _engine()
        # Intercept Serper discovery → return one recruiter + one VP at Mashreq
        # plus one obvious mismatch that must be rejected.
        async def fake_discover(company, role):
            return [
                eng._wayin_parse_serper_item(_serper_item(
                    "Sarah Ahmed", "Head of Talent Acquisition",
                    company_hint="Mashreq Bank",
                    url="https://www.linkedin.com/in/sarah-ahmed",
                ), "q"),
                eng._wayin_parse_serper_item(_serper_item(
                    "Hassan Strategy", "VP of Strategy",
                    company_hint="Mashreq Bank",
                    url="https://www.linkedin.com/in/hassan-strategy",
                ), "q"),
                eng._wayin_parse_serper_item(_serper_item(
                    "Evgeny Wrong", "VP Engineering",
                    company_hint="Yandex",
                    url="https://www.linkedin.com/in/evgeny",
                ), "q"),
            ]

        monkeypatch.setattr(eng, "_wayin_discover", fake_discover)
        # No DB-side mutuals.
        eng.db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: [])
        ))
        # No LLM in tests.
        monkeypatch.setattr(eng, "_craft_message", lambda **kw: "")

        # User's network includes the recruiter as a 1st-degree connection.
        conns = [_make_conn(
            "Sarah Ahmed",
            company="Mashreq Bank",
            title="Head of Talent",
            url="https://www.linkedin.com/in/sarah-ahmed",
        )]

        out = await eng._find_key_people("Mashreq Bank", "VP Strategy", conns, "")
        names = [p["name"] for p in out]

        # Expected outcomes per the spec:
        assert "Sarah Ahmed" in names              # discovered + 1st degree
        assert "Hassan Strategy" in names          # accepted hiring authority
        assert "Evgeny Wrong" not in names         # company mismatch rejected
        # No fabricated "Recruiter — Mashreq Bank" stub.
        assert all(not n.startswith("Recruiter —") for n in names)
        # 1st-degree wins ranking after degree bonus.
        assert out[0]["name"] == "Sarah Ahmed"
        assert out[0]["degree"] == "1st"


# ── domain detection sanity ──────────────────────────────────────────────────


class TestDetectDomain:
    def test_strategy_titles_classify_as_strategy(self):
        assert detect_domain("VP Strategy & Operations") == "strategy"
        assert detect_domain("Chief of Staff") == "strategy"

    def test_hr_titles_classify_as_hr(self):
        assert detect_domain("Head of Talent Acquisition") == "hr"
        assert detect_domain("Senior Recruiter") == "hr"
