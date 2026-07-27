from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.schemas.canonical.common import (
    CompetitionCode,
    SourceReference,
    StrictCanonicalModel,
)


class CanonicalCompetition(StrictCanonicalModel):
    """Competition, season or series supplied by a provider."""

    external_id: str = Field(min_length=1, max_length=160)
    competition_code: CompetitionCode
    name: str = Field(min_length=1, max_length=180)
    season: Optional[str] = Field(default=None, max_length=80)
    series: Optional[str] = Field(default=None, max_length=80)
    week: Optional[str] = Field(default=None, max_length=80)
    group: Optional[str] = Field(default=None, max_length=80)
    stage: Optional[str] = Field(default=None, max_length=120)
    source: SourceReference
