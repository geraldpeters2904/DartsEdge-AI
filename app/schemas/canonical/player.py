from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field

from app.schemas.canonical.common import SourceReference, StrictCanonicalModel


class CanonicalPlayer(StrictCanonicalModel):
    """Provider-independent player record."""

    external_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=180)
    country_code: Optional[str] = Field(default=None, min_length=2, max_length=3)
    nickname: Optional[str] = Field(default=None, max_length=120)
    date_of_birth: Optional[date] = None
    handedness: Optional[str] = Field(default=None, pattern="^(left|right|unknown)$")
    source: SourceReference
