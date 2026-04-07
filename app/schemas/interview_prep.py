"""
app/schemas/interview_prep.py

Pydantic response schemas for the Interview Prep endpoint.

Extracts and restructures the interview data already generated
by the LLM (stored in JobRun.reports.application) into a
frontend-friendly format.
"""

from pydantic import BaseModel, Field


class InterviewStageResponse(BaseModel):
    stage: str = ""
    format: str = ""
    who: str = ""
    duration: str = ""
    what_to_expect: str = ""


class BehaviouralQuestionResponse(BaseModel):
    question: str = ""
    why_they_ask: str = ""
    your_story: str = ""
    key_points: list[str] = Field(default_factory=list)


class BusinessCaseQuestionResponse(BaseModel):
    question: str = ""
    case_type: str = ""
    how_to_frame: str = ""
    watch_out: str = ""


class SituationalQuestionResponse(BaseModel):
    question: str = ""
    what_they_want: str = ""
    suggested_answer_angle: str = ""


class CultureQuestionResponse(BaseModel):
    question: str = ""
    ideal_answer_angle: str = ""


class QuestionBankResponse(BaseModel):
    behavioural: list[BehaviouralQuestionResponse] = Field(default_factory=list)
    business_case: list[BusinessCaseQuestionResponse] = Field(default_factory=list)
    situational: list[SituationalQuestionResponse] = Field(default_factory=list)
    culture_and_motivation: list[CultureQuestionResponse] = Field(default_factory=list)


class QuestionToAskResponse(BaseModel):
    question: str = ""
    why_powerful: str = ""


class ThirtySixtyNinetyResponse(BaseModel):
    thirty: str = ""
    sixty: str = ""
    ninety: str = ""


class InterviewPrepResponse(BaseModel):
    """Full interview prep pack extracted from a completed JobRun."""
    job_run_id: str
    role_title: str | None = None
    company_name: str | None = None

    # Interview process
    interview_stages: list[InterviewStageResponse] = Field(default_factory=list)

    # Question bank (4 categories)
    question_bank: QuestionBankResponse = Field(default_factory=QuestionBankResponse)

    # Questions the candidate should ask the interviewer
    questions_to_ask: list[QuestionToAskResponse] = Field(default_factory=list)

    # Themes to prepare for
    prep_themes: list[str] = Field(default_factory=list)

    # 30-60-90 day plan
    thirty_sixty_ninety: ThirtySixtyNinetyResponse = Field(
        default_factory=ThirtySixtyNinetyResponse,
    )

    # Positioning
    positioning_headline: str = ""
    cover_letter_angle: str = ""
    risks_to_address: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
