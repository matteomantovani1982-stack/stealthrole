"""
app/models/__init__.py

Re-exports all ORM models.
Alembic's env.py imports Base from here to detect all tables.
Add new models to this file as they are created.
"""

from app.models.action_recommendation import ActionRecommendation
from app.models.application import Application, ApplicationStage
from app.models.application_event import ApplicationEvent
from app.models.application_timeline import ApplicationTimeline
from app.models.auto_apply import AutoApplyProfile, AutoApplySubmission
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.calendar_event import CalendarEvent
from app.models.credits import CreditBalance, CreditTransaction
from app.models.cv import CV, CVStatus
from app.models.email_account import EmailAccount, EmailProvider, SyncStatus
from app.models.email_intelligence import EmailIntelligence
from app.models.email_scan import DetectedStage, EmailScan, ScanConfidence
from app.models.hidden_signal import HiddenSignal
from app.models.interview import CompensationBenchmark, InterviewRound
from app.models.job_run import JobRun, JobRunStatus
from app.models.job_step import JobStep, StepName, StepStatus
from app.models.linkedin_connection import LinkedInConnection
from app.models.linkedin_conversation import LinkedInConversation
from app.models.linkedin_message import LinkedInMessage
from app.models.mutual_connection import MutualConnection
from app.models.propagation_adjustment import PropagationAdjustment
from app.models.saved_job import SavedJob
from app.models.scout_result import ScoutResult
from app.models.shadow_application import ShadowApplication
from app.models.signal_interpretation import SignalInterpretation
from app.models.user_intelligence import UserIntelligence
from app.models.warm_intro import IntroStatus, WarmIntro

__all__ = [
    "ActionRecommendation",
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "CV",
    "CVStatus",
    "JobRun",
    "JobRunStatus",
    "JobStep",
    "StepName",
    "StepStatus",
    "ScoutResult",
    "HiddenSignal",
    "ApplicationEvent",
    "SavedJob",
    "Application",
    "ApplicationStage",
    "EmailAccount",
    "EmailProvider",
    "SyncStatus",
    "EmailScan",
    "DetectedStage",
    "ScanConfidence",
    "ApplicationTimeline",
    "CalendarEvent",
    "LinkedInConnection",
    "LinkedInConversation",
    "LinkedInMessage",
    "WarmIntro",
    "IntroStatus",
    "AutoApplyProfile",
    "AutoApplySubmission",
    "InterviewRound",
    "CompensationBenchmark",
    "EmailIntelligence",
    "UserIntelligence",
    "CreditBalance",
    "CreditTransaction",
    "ShadowApplication",
    "MutualConnection",
    "SignalInterpretation",
    "PropagationAdjustment",
    "User",
]

from app.models.user import User
