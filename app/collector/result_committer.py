from __future__ import annotations

import json
from typing import Iterable

from app.collector.commit_helpers import (
    find_match_by_external_id,
    optional_participant_name,
    participant_name,
    player_name_for_external_id,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.schemas.canonical import CanonicalMatchResult
from app.services.canonical_data_service import (
    map_entity,
    record_provenance,
    store_raw,
)


class ResultCommitter:
    """Update existing fixtures from canonical result records."""

    def commit(
        self,
        *,
        db,
        provider: str,
        results: Iterable[CanonicalMatchResult],
        batch: HistoricalImportBatch,
    ) -> None:
        rejected = 0

        for result in results:
            try:
                self._commit_one(
                    db=db,
                    provider=provider,
                    result=result,
                    batch=batch,
                )
            except Exception as exc:
                rejected += 1

                db.add(
                    HistoricalImportItem(
                        batch_id=batch.id,
                        entity_type="result",
                        external_id=result.match_external_id,
                        action="rejected",
                        detail=str(exc),
                        created_by_batch=False,
                    )
                )

        batch.rejected_rows = (
            int(batch.rejected_rows or 0)
            + rejected
        )

    def _commit_one(
        self,
        *,
        db,
        provider: str,
        result: CanonicalMatchResult,
        batch: HistoricalImportBatch,
    ) -> None:
        match = find_match_by_external_id(
            db=db,
            provider=provider,
            match_external_id=result.match_external_id,
        )

        if match is None:
            raise ValueError(
                "No existing fixture mapping was found for "
                f"{result.match_external_id}."
            )

        player_a_name = player_name_for_external_id(
            db=db,
            provider=provider,
            external_id=result.player_a_external_id,
            fallback=match.player_a,
        )
        player_b_name = player_name_for_external_id(
            db=db,
            provider=provider,
            external_id=result.player_b_external_id,
            fallback=match.player_b,
        )

        expected_winner = participant_name(
            external_id=result.winner_external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )
        expected_first_leg_winner = optional_participant_name(
            external_id=result.first_leg_winner_external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )
        expected_first_180_player = optional_participant_name(
            external_id=result.first_180_player_external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )
        expected_score = (
            f"{result.player_a_legs}-{result.player_b_legs}"
        )

        raw_record, _ = store_raw(
            db,
            provider,
            "result",
            result.match_external_id,
            result.model_dump(mode="json"),
        )

        if self._is_duplicate(
            match=match,
            winner=expected_winner,
            score=expected_score,
            first_leg_winner=expected_first_leg_winner,
            first_180_player=expected_first_180_player,
        ):
            raw_record.processed = True

            db.add(
                HistoricalImportItem(
                    batch_id=batch.id,
                    entity_type="result",
                    internal_id=match.id,
                    external_id=result.match_external_id,
                    action="duplicate",
                    detail="Match already contains the identical result.",
                    created_by_batch=False,
                )
            )
            return

        previous_state = {
            "status": match.status,
            "winner": match.winner,
            "score": match.score,
            "first_leg_winner": match.first_leg_winner,
            "first_180_player": match.first_180_player,
        }

        match.player_a = player_a_name
        match.player_b = player_b_name
        match.status = "completed"
        match.score = expected_score
        match.winner = expected_winner
        match.first_leg_winner = expected_first_leg_winner
        match.first_180_player = expected_first_180_player

        db.flush()

        map_entity(
            db,
            provider,
            "result",
            result.match_external_id,
            match.id,
        )

        for field_name in (
            "status",
            "winner",
            "score",
            "first_leg_winner",
            "first_180_player",
        ):
            record_provenance(
                db,
                "result",
                match.id,
                field_name,
                provider,
                result.match_external_id,
                confidence=result.source.confidence.value,
            )

        raw_record.processed = True

        db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="result",
                internal_id=match.id,
                external_id=result.match_external_id,
                action="updated",
                detail=json.dumps(
                    {
                        "previous": previous_state,
                        "current": {
                            "status": match.status,
                            "winner": match.winner,
                            "score": match.score,
                            "first_leg_winner": match.first_leg_winner,
                            "first_180_player": match.first_180_player,
                        },
                    },
                    sort_keys=True,
                ),
                created_by_batch=False,
            )
        )

    @staticmethod
    def _is_duplicate(
        *,
        match,
        winner: str,
        score: str,
        first_leg_winner,
        first_180_player,
    ) -> bool:
        return (
            match.status == "completed"
            and match.winner == winner
            and match.score == score
            and match.first_leg_winner == first_leg_winner
            and match.first_180_player == first_180_player
        )