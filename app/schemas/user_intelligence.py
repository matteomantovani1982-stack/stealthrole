"""app/schemas/user_intelligence.py"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_strength: int
    strength_breakdown: dict | None = None
    behavioral_profile: dict | None = None
    success_patterns: dict | None = None
    failure_patterns: dict | None = None
    recommendations: dict | None = None
    updated_at: datetime
