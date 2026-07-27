from __future__ import annotations

import json
from typing import Iterable, Optional

from app.collector.commit_helpers import find_match_by_external_id
from app.models.canonical_data import ProviderEntityMapping
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.schemas.canonical import CanonicalPlayerMatchStatistics
from app.services.canonical_data_service import (
    map_entity,
    record_provenance,
    store_raw,
)


class StatisticsCommitter:
    """Store immutable statistics for one player in one match."""

    def commit(
        self,
        *,
        db,
        provider: str,
        statistics: Iterable[CanonicalPlayerMatchStatistics],
        batch: HistoricalImportBatch,
    ) -> None:
        rejected = 0

        for record in statistics:
            try:
                self._commit_one(
                    db=db,
                    provider=provider,
                    record=record,
                    batch=batch,
                )
            except Exception as exc:
                rejected += 1

                db.add(
                    HistoricalImportItem(
                        batch_id=batch.id,
                        entity_type="match_stats",
                        external_id=record.source.external_id,
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
        record: CanonicalPlayerMatchStatistics,
        batch: HistoricalImportBatch,
    ) -> None:
        match = find_match_by_external_id(
            db=db,
            provider=provider,
            match_external_id=record.match_external_id,
        )

        if match is None:
            raise ValueError(
                "No existing fixture mapping was found for "
                f"{record.match_external_id}."
            )

        player = self._find_player(
            db=db,
            provider=provider,
            player_external_id=record.player_external_id,
        )

        if player is None:
            raise ValueError(
                "No existing player mapping was found for "
                f"{record.player_external_id}."
            )

        opponent = self._find_opponent(
            db=db,
            match=match,
            player=player,
        )

        raw_record, _ = store_raw(
            db,
            provider,
            "match_stats",
            record.source.external_id,
            record.model_dump(mode="json"),
        )

        values = self._performance_values(
            record=record,
            match=match,
            player=player,
            opponent=opponent,
        )

        existing = (
            db.query(PlayerMatchPerformance)
            .filter_by(
                match_id=match.id,
                player_id=player.id,
            )
            .first()
        )

        if existing is not None:
            if self._same_observation(existing, values):
                raw_record.processed = True

                db.add(
                    HistoricalImportItem(
                        batch_id=batch.id,
                        entity_type="player_match_performance",
                        internal_id=existing.id,
                        external_id=record.source.external_id,
                        action="duplicate",
                        detail=(
                            "Identical player-match performance "
                            "already exists."
                        ),
                        created_by_batch=False,
                    )
                )
                return

            raise ValueError(
                "A different performance record already exists for "
                "this player and match. Immutable history was not "
                "overwritten."
            )

        performance = PlayerMatchPerformance(**values)

        db.add(performance)
        db.flush()

        map_entity(
            db,
            provider,
            "match_stats",
            record.source.external_id,
            performance.id,
            record.source.competition_code,
        )

        for field_name in self._observed_field_names(record):
            record_provenance(
                db,
                "match_stats",
                performance.id,
                field_name,
                provider,
                record.source.external_id,
                confidence=record.source.confidence.value,
            )

        raw_record.processed = True

        db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="player_match_performance",
                internal_id=performance.id,
                external_id=record.source.external_id,
                action="created",
                detail=json.dumps(
                    {
                        "match_external_id": (
                            record.match_external_id
                        ),
                        "player_external_id": (
                            record.player_external_id
                        ),
                    },
                    sort_keys=True,
                ),
                created_by_batch=True,
            )
        )

    @staticmethod
    def _find_player(
        *,
        db,
        provider: str,
        player_external_id: str,
    ) -> Optional[Player]:
        mapping = (
            db.query(ProviderEntityMapping)
            .filter_by(
                provider=provider,
                entity_type="player",
                external_id=player_external_id,
            )
            .first()
        )

        if mapping is None:
            return None

        return (
            db.query(Player)
            .filter(Player.id == mapping.internal_id)
            .first()
        )

    @staticmethod
    def _find_opponent(
        *,
        db,
        match,
        player,
    ) -> Optional[Player]:
        if match.player_a == player.name:
            opponent_name = match.player_b
        elif match.player_b == player.name:
            opponent_name = match.player_a
        else:
            raise ValueError(
                f"Mapped player {player.name} is not a participant "
                f"in match {match.id}."
            )

        return (
            db.query(Player)
            .filter(Player.name == opponent_name)
            .first()
        )

    @staticmethod
    def _performance_values(
        *,
        record,
        match,
        player,
        opponent,
    ) -> dict:
        won_match = None

        if match.winner:
            won_match = match.winner == player.name

        return {
            "match_id": match.id,
            "player_id": player.id,
            "opponent_id": (
                opponent.id
                if opponent is not None
                else None
            ),
            "competition_code": (
                record.source.competition_code
            ),
            "player_external_id": (
                record.player_external_id
            ),
            "won_match": won_match,
            "threw_first": None,
            "legs_won": record.legs_won,
            "legs_lost": record.legs_lost,
            "legs_held": record.legs_held,
            "legs_broken": record.legs_broken,
            "three_dart_average": (
                record.three_dart_average
            ),
            "first_nine_average": (
                record.first_nine_average
            ),
            "scores_100_plus": record.scores_100_plus,
            "scores_140_plus": record.scores_140_plus,
            "scores_180": record.scores_180,
            "checkout_attempts": (
                record.checkout_attempts
            ),
            "checkouts_completed": (
                record.checkouts_completed
            ),
            "checkout_percentage": (
                record.checkout_percentage
            ),
            "highest_checkout": (
                record.highest_checkout
            ),
            "match_duration_seconds": (
                record.match_duration_seconds
            ),
            "source_provider": record.source.provider,
            "source_external_id": (
                record.source.external_id
            ),
            "source_confidence": (
                record.source.confidence.value
            ),
            "observed_at": record.source.retrieved_at,
        }

    @staticmethod
    def _same_observation(
        existing,
        values: dict,
    ) -> bool:
        fields = (
            "opponent_id",
            "competition_code",
            "player_external_id",
            "won_match",
            "legs_won",
            "legs_lost",
            "legs_held",
            "legs_broken",
            "three_dart_average",
            "first_nine_average",
            "scores_100_plus",
            "scores_140_plus",
            "scores_180",
            "checkout_attempts",
            "checkouts_completed",
            "checkout_percentage",
            "highest_checkout",
            "match_duration_seconds",
            "source_provider",
            "source_external_id",
            "source_confidence",
        )

        return all(
            getattr(existing, field_name)
            == values[field_name]
            for field_name in fields
        )

    @staticmethod
    def _observed_field_names(
        record,
    ) -> tuple[str, ...]:
        fields = (
            "legs_won",
            "legs_lost",
            "legs_held",
            "legs_broken",
            "three_dart_average",
            "first_nine_average",
            "scores_100_plus",
            "scores_140_plus",
            "scores_180",
            "checkout_attempts",
            "checkouts_completed",
            "checkout_percentage",
            "highest_checkout",
            "match_duration_seconds",
        )

        return tuple(
            field_name
            for field_name in fields
            if getattr(record, field_name) is not None
        )
