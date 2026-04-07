"""
app/models/application_event.py

Timeline event for a job application (JobRun).

Tracks key moments: stage changes, document generation, user actions, etc.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class ApplicationEvent(Base, UUIDMixin):
    __tablename__ = "application_events"

    job_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.now().astimezone().tzinfo),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<ApplicationEvent id={self.id} "
            f"type={self.event_type} title={self.title}>"
        )
