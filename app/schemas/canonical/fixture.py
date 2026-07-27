from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.schemas.canonical.common import (
    CompetitionCode,
    MatchStatus,
    SourceReference,
    StrictCanonicalModel,
)


class CanonicalFixture(StrictCanonicalModel):
    """Scheduled or live darts fixture."""

    external_id: str = Field(min_length=1, max_length=160)
    competition_code: CompetitionCode
    competition_name: str = Field(min_length=1, max_length=180)

    season: Optional[str] = Field(default=None, max_length=80)
    series: Optional[str] = Field(default=None, max_length=80)
    week: Optional[str] = Field(default=None, max_length=80)
    group: Optional[str] = Field(default=None, max_length=80)
    stage: Optional[str] = Field(default=None, max_length=120)

    scheduled_at: datetime
    actual_start_at: Optional[datetime] = None
    status: MatchStatus = MatchStatus.SCHEDULED
    match_format: str = Field(default="Best of 7", min_length=1, max_length=80)
    board: Optional[str] = Field(default=None, max_length=40)
    session: Optional[str] = Field(default=None, max_length=80)

    player_a_external_id: str = Field(min_length=1, max_length=160)
    player_a_name: str = Field(min_length=1, max_length=180)
    player_b_external_id: str = Field(min_length=1, max_length=160)
    player_b_name: str = Field(min_length=1, max_length=180)

    throwing_first_player_external_id: Optional[str] = Field(
        default=None,
        max_length=160,
    )

    source: SourceReference

    @model_validator(mode="after")
    def validate_players(self) -> "CanonicalFixture":
        if self.player_a_external_id == self.player_b_external_id:
            raise ValueError("A fixture must contain two different players.")

        if self.player_a_name.casefold() == self.player_b_name.casefold():
            raise ValueError("Player A and Player B must have different names.")

        if self.throwing_first_player_external_id is not None:
            valid_ids = {
                self.player_a_external_id,
                self.player_b_external_id,
            }
            if self.throwing_first_player_external_id not in valid_ids:
                raise ValueError(
                    "The player throwing first must be one of the fixture players."
                )

        return self
