from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictCanonicalModel(BaseModel):
    """Base class for provider-independent canonical records."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class CompetitionCode(str, Enum):
    MODUS = "MODUS"
    PDC = "PDC"
    WDF = "WDF"
    ADC = "ADC"
    CDC = "CDC"
    OTHER = "OTHER"


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class RecordConfidence(str, Enum):
    REPORTED = "reported"
    VERIFIED = "verified"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    MANUAL = "manual"


class SourceReference(StrictCanonicalModel):
    """Identifies where a canonical record originated."""

    provider: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=160)
    retrieved_at: datetime
    competition_code: Optional[CompetitionCode] = None
    confidence: RecordConfidence = RecordConfidence.REPORTED
