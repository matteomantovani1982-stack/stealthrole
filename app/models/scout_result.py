"""
app/models/scout_result.py

Persistent storage for Scout signal engine results.
Allows caching of expensive signal scans and historical trend tracking.
"""


from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ScoutResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scout_results"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # The full response cached
    opportunities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    live_openings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    signals_detected: Mapped[int] = mapped_column(Integer, default=0)
    sources_searched: Mapped[int] = mapped_column(Integer, default=0)
    scored_by: Mapped[str] = mapped_column(String, default="")

    # Search parameters used
    regions: Mapped[dict] = mapped_column(JSONB, default=list)
    roles: Mapped[dict] = mapped_column(JSONB, default=list)
    sectors: Mapped[dict] = mapped_column(JSONB, default=list)

    # Validity
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<ScoutResult id={self.id} user_id={self.user_id} "
            f"signals={self.signals_detected} stale={self.is_stale}>"
        )
