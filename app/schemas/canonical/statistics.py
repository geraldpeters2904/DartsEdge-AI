from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from app.schemas.canonical.common import SourceReference, StrictCanonicalModel


class CanonicalPlayerMatchStatistics(StrictCanonicalModel):
    """
    Statistics for one player in one match.

    Missing provider values must remain None. A value of zero means that the
    provider explicitly reported zero.
    """

    match_external_id: str = Field(min_length=1, max_length=160)
    player_external_id: str = Field(min_length=1, max_length=160)

    three_dart_average: Optional[float] = Field(default=None, ge=0, le=180)
    first_nine_average: Optional[float] = Field(default=None, ge=0, le=180)

    scores_100_plus: Optional[int] = Field(default=None, ge=0)
    scores_140_plus: Optional[int] = Field(default=None, ge=0)
    scores_180: Optional[int] = Field(default=None, ge=0)

    checkout_attempts: Optional[int] = Field(default=None, ge=0)
    checkouts_completed: Optional[int] = Field(default=None, ge=0)
    checkout_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    highest_checkout: Optional[int] = Field(default=None, ge=0, le=170)

    legs_won: Optional[int] = Field(default=None, ge=0)
    legs_lost: Optional[int] = Field(default=None, ge=0)
    legs_held: Optional[int] = Field(default=None, ge=0)
    legs_broken: Optional[int] = Field(default=None, ge=0)

    match_duration_seconds: Optional[int] = Field(default=None, ge=0)

    source: SourceReference

    @model_validator(mode="after")
    def validate_checkout_values(self) -> "CanonicalPlayerMatchStatistics":
        attempts = self.checkout_attempts
        completed = self.checkouts_completed

        if (
            attempts is not None
            and completed is not None
            and completed > attempts
        ):
            raise ValueError(
                "checkouts_completed cannot exceed checkout_attempts."
            )

        return self
