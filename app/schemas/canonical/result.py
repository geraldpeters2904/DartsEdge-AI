from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.schemas.canonical.common import SourceReference, StrictCanonicalModel


class CanonicalMatchResult(StrictCanonicalModel):
    """Final result linked to a canonical fixture."""

    match_external_id: str = Field(min_length=1, max_length=160)

    player_a_external_id: str = Field(min_length=1, max_length=160)
    player_b_external_id: str = Field(min_length=1, max_length=160)
    winner_external_id: str = Field(min_length=1, max_length=160)

    player_a_legs: int = Field(ge=0)
    player_b_legs: int = Field(ge=0)

    completed_at: Optional[datetime] = None
    first_leg_winner_external_id: Optional[str] = Field(
        default=None,
        max_length=160,
    )
    first_180_player_external_id: Optional[str] = Field(
        default=None,
        max_length=160,
    )

    source: SourceReference

    @model_validator(mode="after")
    def validate_result(self) -> "CanonicalMatchResult":
        players = {
            self.player_a_external_id,
            self.player_b_external_id,
        }

        if len(players) != 2:
            raise ValueError("A result must contain two different players.")

        if self.winner_external_id not in players:
            raise ValueError("The winner must be one of the match players.")

        if self.player_a_legs == self.player_b_legs:
            raise ValueError("A completed darts match cannot finish as a draw.")

        expected_winner = (
            self.player_a_external_id
            if self.player_a_legs > self.player_b_legs
            else self.player_b_external_id
        )
        if self.winner_external_id != expected_winner:
            raise ValueError("Winner does not agree with the final leg score.")

        for field_name in (
            "first_leg_winner_external_id",
            "first_180_player_external_id",
        ):
            value = getattr(self, field_name)
            if value is not None and value not in players:
                raise ValueError(
                    f"{field_name} must identify one of the match players."
                )

        return self
