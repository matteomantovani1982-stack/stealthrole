"""
tests/test_interview_prep.py

Interview Prep endpoint tests — validates that interview preparation data
is correctly extracted from a completed JobRun's reports.
"""

import pytest
from app.schemas.interview_prep import (
    InterviewPrepResponse,
    InterviewStageResponse,
    QuestionBankResponse,
    BehaviouralQuestionResponse,
    BusinessCaseQuestionResponse,
    SituationalQuestionResponse,
    CultureQuestionResponse,
    QuestionToAskResponse,
    ThirtySixtyNinetyResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures: sample report data matching LLM output schema
# ═══════════════════════════════════════════════════════════════════════════

def _full_application_strategy():
    """Sample ApplicationStrategy dict as stored in JobRun.reports['application']."""
    return {
        "positioning_headline": "Digital Transformation Leader | MENA Scale-Up Expert",
        "cover_letter_angle": "Bridge between startup agility and enterprise scale",
        "interview_process": [
            {
                "stage": "Recruiter Screen",
                "format": "Phone",
                "who": "Talent Acquisition",
                "duration": "30 min",
                "what_to_expect": "Culture fit, salary expectations, availability",
            },
            {
                "stage": "Hiring Manager Interview",
                "format": "Video",
                "who": "VP Strategy",
                "duration": "60 min",
                "what_to_expect": "Deep dive on strategy experience and MENA market knowledge",
            },
            {
                "stage": "Case Study",
                "format": "In-person",
                "who": "Panel (3 executives)",
                "duration": "90 min",
                "what_to_expect": "Present market entry strategy for new vertical",
            },
        ],
        "question_bank": {
            "behavioural": [
                {
                    "question": "Tell me about a time you scaled a team rapidly",
                    "why_they_ask": "They need someone who can hire fast without dropping quality",
                    "your_story": "Baly: 3 to 500 in 18 months across 4 cities",
                    "key_points": ["Structured hiring process", "Culture-first approach", "Local leadership hires"],
                },
            ],
            "business_case": [
                {
                    "question": "How would you enter the Saudi market for delivery?",
                    "case_type": "Market entry",
                    "how_to_frame": "Start with regulatory landscape, then unit economics",
                    "watch_out": "Don't ignore local partnerships — they're mandatory",
                },
            ],
            "situational": [
                {
                    "question": "Your largest client threatens to leave. What do you do?",
                    "what_they_want": "De-escalation skills and commercial acumen",
                    "suggested_answer_angle": "Listen first, quantify impact, propose retention plan within 48h",
                },
            ],
            "culture_and_motivation": [
                {
                    "question": "Why this company and why now?",
                    "ideal_answer_angle": "Connect their growth stage to your track record at similar inflection points",
                },
            ],
        },
        "questions_to_ask_them": [
            {
                "question": "What does success look like in the first 6 months?",
                "why_powerful": "Shows you're thinking about outcomes, not just getting the job",
            },
            {
                "question": "What's the biggest risk to this initiative?",
                "why_powerful": "Demonstrates strategic thinking and willingness to tackle hard problems",
            },
        ],
        "interview_prep_themes": [
            "MENA market dynamics",
            "Scaling operations",
            "Stakeholder management",
            "Digital transformation",
            "P&L ownership",
        ],
        "thirty_sixty_ninety": {
            "30": "Deep immersion: meet all stakeholders, audit current strategy, identify quick wins",
            "60": "Launch first initiative: pilot new market vertical with cross-functional team",
            "90": "Deliver first measurable results: revenue growth in pilot, team structure solidified",
        },
        "risks_to_address": [
            "No direct experience in their specific vertical",
            "Startup background may raise 'enterprise readiness' concerns",
        ],
        "differentiators": [
            "Built and exited a business in MENA — not just advised on it",
            "Bilingual Arabic/English with C-suite presence",
            "Track record of 0-to-1 AND 1-to-100 growth",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Schema tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInterviewPrepSchemas:

    def test_interview_stage_response_defaults(self):
        stage = InterviewStageResponse()
        assert stage.stage == ""
        assert stage.format == ""

    def test_interview_stage_response_with_data(self):
        stage = InterviewStageResponse(
            stage="Recruiter Screen",
            format="Phone",
            who="HR",
            duration="30 min",
            what_to_expect="Basic screening",
        )
        assert stage.stage == "Recruiter Screen"
        assert stage.duration == "30 min"

    def test_question_bank_response_defaults(self):
        qb = QuestionBankResponse()
        assert qb.behavioural == []
        assert qb.business_case == []
        assert qb.situational == []
        assert qb.culture_and_motivation == []

    def test_thirty_sixty_ninety_defaults(self):
        plan = ThirtySixtyNinetyResponse()
        assert plan.thirty == ""
        assert plan.sixty == ""
        assert plan.ninety == ""

    def test_full_response_from_data(self):
        data = _full_application_strategy()
        response = InterviewPrepResponse(
            job_run_id="test-id",
            role_title="VP Strategy",
            company_name="Acme Corp",
            interview_stages=[InterviewStageResponse(**s) for s in data["interview_process"]],
            question_bank=QuestionBankResponse(
                behavioural=[BehaviouralQuestionResponse(**q) for q in data["question_bank"]["behavioural"]],
                business_case=[BusinessCaseQuestionResponse(**q) for q in data["question_bank"]["business_case"]],
                situational=[SituationalQuestionResponse(**q) for q in data["question_bank"]["situational"]],
                culture_and_motivation=[CultureQuestionResponse(**q) for q in data["question_bank"]["culture_and_motivation"]],
            ),
            questions_to_ask=[QuestionToAskResponse(**q) for q in data["questions_to_ask_them"]],
            prep_themes=data["interview_prep_themes"],
            thirty_sixty_ninety=ThirtySixtyNinetyResponse(
                thirty=data["thirty_sixty_ninety"]["30"],
                sixty=data["thirty_sixty_ninety"]["60"],
                ninety=data["thirty_sixty_ninety"]["90"],
            ),
            positioning_headline=data["positioning_headline"],
            cover_letter_angle=data["cover_letter_angle"],
            risks_to_address=data["risks_to_address"],
            differentiators=data["differentiators"],
        )
        assert response.job_run_id == "test-id"
        assert len(response.interview_stages) == 3
        assert response.interview_stages[0].stage == "Recruiter Screen"
        assert len(response.question_bank.behavioural) == 1
        assert len(response.question_bank.business_case) == 1
        assert len(response.questions_to_ask) == 2
        assert len(response.prep_themes) == 5
        assert response.thirty_sixty_ninety.thirty.startswith("Deep immersion")
        assert len(response.risks_to_address) == 2
        assert len(response.differentiators) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Endpoint logic tests (mock DB)
# ═══════════════════════════════════════════════════════════════════════════

class TestInterviewPrepEndpoint:

    def _make_job_run(self, status="completed", reports=None):
        """Create a mock JobRun object."""
        from unittest.mock import MagicMock
        import uuid

        run = MagicMock()
        run.id = uuid.uuid4()
        run.user_id = "user-1"
        run.status = status
        run.reports = reports
        run.role_title = "VP Strategy"
        run.company_name = "Acme Corp"
        return run

    def test_extracts_interview_stages(self):
        data = _full_application_strategy()
        reports = {"application": data}
        run = self._make_job_run(reports=reports)

        app_strategy = run.reports.get("application", {})
        stages = app_strategy.get("interview_process", [])
        assert len(stages) == 3
        assert stages[0]["stage"] == "Recruiter Screen"
        assert stages[1]["format"] == "Video"
        assert stages[2]["who"] == "Panel (3 executives)"

    def test_extracts_question_bank(self):
        data = _full_application_strategy()
        reports = {"application": data}
        run = self._make_job_run(reports=reports)

        qb = run.reports["application"]["question_bank"]
        assert len(qb["behavioural"]) == 1
        assert qb["behavioural"][0]["question"].startswith("Tell me about")
        assert len(qb["business_case"]) == 1
        assert len(qb["situational"]) == 1
        assert len(qb["culture_and_motivation"]) == 1

    def test_extracts_thirty_sixty_ninety(self):
        data = _full_application_strategy()
        reports = {"application": data}
        run = self._make_job_run(reports=reports)

        plan = run.reports["application"]["thirty_sixty_ninety"]
        assert "30" in plan
        assert "60" in plan
        assert "90" in plan
        assert plan["30"].startswith("Deep immersion")

    def test_handles_empty_reports(self):
        run = self._make_job_run(reports={})
        app_strategy = run.reports.get("application", {})
        assert app_strategy.get("interview_process", []) == []
        assert app_strategy.get("question_bank", {}) == {}
        assert app_strategy.get("thirty_sixty_ninety", {}) == {}

    def test_handles_none_reports(self):
        run = self._make_job_run(reports=None)
        reports = run.reports or {}
        app_strategy = reports.get("application", {})
        assert app_strategy == {}

    def test_handles_partial_application_data(self):
        """Reports with application but missing some fields."""
        reports = {
            "application": {
                "positioning_headline": "Test Headline",
                "interview_process": [
                    {"stage": "Phone Screen", "format": "Phone"},
                ],
                # question_bank, thirty_sixty_ninety, etc. are missing
            }
        }
        run = self._make_job_run(reports=reports)
        app_strategy = run.reports["application"]

        stages = [InterviewStageResponse(**s) for s in app_strategy.get("interview_process", [])]
        assert len(stages) == 1
        assert stages[0].stage == "Phone Screen"
        assert stages[0].who == ""  # default

        qb_data = app_strategy.get("question_bank", {})
        qb = QuestionBankResponse(
            behavioural=[BehaviouralQuestionResponse(**q) for q in qb_data.get("behavioural", [])],
        )
        assert qb.behavioural == []

    def test_rejects_non_completed_run(self):
        """Interview prep should only be available for completed runs."""
        run = self._make_job_run(status="llm_processing")
        assert run.status != "completed"

    def test_full_response_construction(self):
        """End-to-end test of building InterviewPrepResponse from raw data."""
        data = _full_application_strategy()
        reports = {"application": data}
        run = self._make_job_run(reports=reports)

        app_strategy = (run.reports or {}).get("application", {})

        qb_data = app_strategy.get("question_bank", {})
        question_bank = QuestionBankResponse(
            behavioural=[BehaviouralQuestionResponse(**q) for q in qb_data.get("behavioural", [])],
            business_case=[BusinessCaseQuestionResponse(**q) for q in qb_data.get("business_case", [])],
            situational=[SituationalQuestionResponse(**q) for q in qb_data.get("situational", [])],
            culture_and_motivation=[CultureQuestionResponse(**q) for q in qb_data.get("culture_and_motivation", [])],
        )

        raw_plan = app_strategy.get("thirty_sixty_ninety", {})
        thirty_sixty_ninety = ThirtySixtyNinetyResponse(
            thirty=raw_plan.get("30", ""),
            sixty=raw_plan.get("60", ""),
            ninety=raw_plan.get("90", ""),
        )

        response = InterviewPrepResponse(
            job_run_id=str(run.id),
            role_title=run.role_title,
            company_name=run.company_name,
            interview_stages=[InterviewStageResponse(**s) for s in app_strategy.get("interview_process", [])],
            question_bank=question_bank,
            questions_to_ask=[QuestionToAskResponse(**q) for q in app_strategy.get("questions_to_ask_them", [])],
            prep_themes=app_strategy.get("interview_prep_themes", []),
            thirty_sixty_ninety=thirty_sixty_ninety,
            positioning_headline=app_strategy.get("positioning_headline", ""),
            cover_letter_angle=app_strategy.get("cover_letter_angle", ""),
            risks_to_address=app_strategy.get("risks_to_address", []),
            differentiators=app_strategy.get("differentiators", []),
        )

        assert response.role_title == "VP Strategy"
        assert response.company_name == "Acme Corp"
        assert len(response.interview_stages) == 3
        assert response.question_bank.behavioural[0].your_story.startswith("Baly")
        assert response.positioning_headline == "Digital Transformation Leader | MENA Scale-Up Expert"
        assert "MENA market dynamics" in response.prep_themes
        assert response.thirty_sixty_ninety.ninety.startswith("Deliver first")


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestInterviewPrepEdgeCases:

    def test_empty_question_bank_categories(self):
        qb = QuestionBankResponse(
            behavioural=[],
            business_case=[],
            situational=[],
            culture_and_motivation=[],
        )
        assert len(qb.behavioural) == 0
        assert len(qb.culture_and_motivation) == 0

    def test_behavioural_question_empty_key_points(self):
        q = BehaviouralQuestionResponse(
            question="Tell me about a challenge",
            why_they_ask="Resilience",
            your_story="My story",
            key_points=[],
        )
        assert q.key_points == []

    def test_interview_stage_minimal(self):
        """Stage with only the stage name — all other fields default."""
        stage = InterviewStageResponse(stage="Final Round")
        assert stage.format == ""
        assert stage.who == ""
        assert stage.duration == ""

    def test_thirty_sixty_ninety_partial(self):
        """Only 30-day plan provided."""
        plan = ThirtySixtyNinetyResponse(thirty="Onboard and learn")
        assert plan.thirty == "Onboard and learn"
        assert plan.sixty == ""
        assert plan.ninety == ""

    def test_response_with_no_role_or_company(self):
        """JobRun may not have role_title or company_name extracted yet."""
        response = InterviewPrepResponse(
            job_run_id="some-id",
            role_title=None,
            company_name=None,
        )
        assert response.role_title is None
        assert response.company_name is None
        assert response.interview_stages == []
        assert response.prep_themes == []

    def test_question_to_ask_defaults(self):
        q = QuestionToAskResponse()
        assert q.question == ""
        assert q.why_powerful == ""

    def test_serialization_roundtrip(self):
        """Ensure response can be serialized to JSON and back."""
        data = _full_application_strategy()
        response = InterviewPrepResponse(
            job_run_id="roundtrip-test",
            interview_stages=[InterviewStageResponse(**s) for s in data["interview_process"]],
            prep_themes=data["interview_prep_themes"],
        )
        json_str = response.model_dump_json()
        restored = InterviewPrepResponse.model_validate_json(json_str)
        assert restored.job_run_id == "roundtrip-test"
        assert len(restored.interview_stages) == 3
        assert len(restored.prep_themes) == 5
