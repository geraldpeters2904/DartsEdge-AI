from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from app.collector.fixture_committer import FixtureCommitter
from app.collector.odds_committer import OddsCommitter
from app.collector.folder_preview import CollectorFolderPreview
from app.collector.result_committer import ResultCommitter
from app.collector.statistics_committer import StatisticsCommitter
from app.models.canonical_data import ProviderEntityMapping
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.models.player import Player
from app.services.player_name_service import resolve_player_by_name
from app.services.paper_trade_service import (
    settle_open_trades_for_fixture,
)
from app.schemas.canonical import (
    CanonicalFixture,
    CanonicalMatchResult,
)
from app.services.canonical_data_service import (
    map_entity,
    record_provenance,
    store_raw,
)


@dataclass(frozen=True)
class CollectorCommitReport:
    """Summary of one collector commit operation."""

    batch: HistoricalImportBatch
    entity_counts: Dict[str, int]

    @property
    def batch_id(self) -> int:
        return self.batch.id

    @property
    def batch_uuid(self) -> str:
        return self.batch.batch_uuid

    @property
    def created_matches(self) -> int:
        return self.batch.created_matches

    @property
    def created_players(self) -> int:
        return self.batch.created_players

    @property
    def duplicate_matches(self) -> int:
        return self.batch.duplicate_matches

    @property
    def rejected_rows(self) -> int:
        return self.batch.rejected_rows


class CollectorCommitBridge:
    """
    Commit validated collector records into the existing DartsEdge warehouse.

    Fixtures continue to use the established historical-import engine so player
    aliases, duplicate checks, batches, provenance and rollback behaviour remain
    centralised.

    Results update an existing fixture. They never create a second match.
    """

    SUPPORTED_ENTITY_TYPES = {
        "fixtures",
        "results",
        "statistics",
        "odds",
    }

    def commit(
        self,
        *,
        db,
        preview: CollectorFolderPreview,
        filename: Optional[str] = None,
    ) -> CollectorCommitReport:
        self._validate_preview(preview)

        fixtures = self._records(preview, "fixtures")
        results = self._records(preview, "results")
        statistics = self._records(preview, "statistics")
        odds = self._records(preview, "odds")

        if not fixtures and not results and not statistics and not odds:
            raise ValueError(
                "The collector preview contains no supported records to commit."
            )

        if fixtures:
            batch = self._commit_fixtures(
                db=db,
                preview=preview,
                fixtures=fixtures,
                filename=filename,
            )
        else:
            batch = self._create_batch(
                db=db,
                preview=preview,
                filename=filename,
                received_rows=(
                    len(results)
                    + len(statistics)
                    + len(odds)
                ),
            )

        if fixtures:
            self._ensure_canonical_player_mappings(
                db=db,
                provider=preview.provider,
                fixtures=fixtures,
            )

        if results:
            self._commit_results(
                db=db,
                provider=preview.provider,
                results=results,
                batch=batch,
            )

            for result in results:
                match = self._find_match(
                    db=db,
                    provider=preview.provider,
                    match_external_id=result.match_external_id,
                )
                if match is None:
                    continue

                settle_open_trades_for_fixture(
                    db,
                    match.id,
                )

        if statistics:
            StatisticsCommitter().commit(
                db=db,
                provider=preview.provider,
                statistics=statistics,
                batch=batch,
            )

        if odds:
            OddsCommitter().commit(
                db=db,
                provider=preview.provider,
                odds=odds,
                batch=batch,
            )

        batch.received_rows = (
            len(fixtures)
            + len(results)
            + len(statistics)
            + len(odds)
        )
        batch.status = "imported"

        db.commit()
        db.refresh(batch)

        return CollectorCommitReport(
            batch=batch,
            entity_counts={
                "fixtures": len(fixtures),
                "results": len(results),
                "statistics": len(statistics),
                "odds": len(odds),
            },
        )

    def _validate_preview(
        self,
        preview: CollectorFolderPreview,
    ) -> None:
        if not isinstance(preview, CollectorFolderPreview):
            raise TypeError(
                "preview must be a CollectorFolderPreview instance."
            )

        if not preview.ready_to_commit:
            raise ValueError(
                "Collector preview is not ready to commit."
            )

        unsupported = (
            set(preview.mappings)
            - self.SUPPORTED_ENTITY_TYPES
        )

        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(
                "This commit-bridge version supports fixtures, results, statistics and odds only. "
                f"Unsupported preview entities: {names}."
            )

    def _commit_fixtures(
        self,
        *,
        db,
        preview: CollectorFolderPreview,
        fixtures: List[CanonicalFixture],
        filename: Optional[str],
    ) -> HistoricalImportBatch:
        return FixtureCommitter().commit(
            db=db,
            provider=preview.provider,
            filename=filename or self._default_filename(
                preview,
                suffix="fixtures",
            ),
            competition=self._competition_code(fixtures),
            fixtures=fixtures,
        )

    def _commit_results(
        self,
        *,
        db,
        provider: str,
        results: Iterable[CanonicalMatchResult],
        batch: HistoricalImportBatch,
    ) -> None:
        ResultCommitter().commit(
            db=db,
            provider=provider,
            results=results,
            batch=batch,
        )

    def _commit_one_result(
        self,
        *,
        db,
        provider: str,
        result: CanonicalMatchResult,
        batch: HistoricalImportBatch,
    ) -> None:
        match = self._find_match(
            db=db,
            provider=provider,
            match_external_id=result.match_external_id,
        )

        if match is None:
            raise ValueError(
                "No existing fixture mapping was found for "
                f"{result.match_external_id}."
            )

        player_a_name = self._player_name_for_external_id(
            db=db,
            provider=provider,
            external_id=result.player_a_external_id,
            fallback=match.player_a,
        )
        player_b_name = self._player_name_for_external_id(
            db=db,
            provider=provider,
            external_id=result.player_b_external_id,
            fallback=match.player_b,
        )

        expected_winner = self._participant_name(
            external_id=result.winner_external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )
        expected_first_leg_winner = self._optional_participant_name(
            external_id=result.first_leg_winner_external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )
        expected_first_180_player = self._optional_participant_name(
            external_id=result.first_180_player_external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )
        expected_score = (
            f"{result.player_a_legs}-{result.player_b_legs}"
        )

        raw_payload = result.model_dump(mode="json")

        raw_record, _ = store_raw(
            db,
            provider,
            "result",
            result.match_external_id,
            raw_payload,
        )

        if (
            match.status == "completed"
            and match.winner == expected_winner
            and match.score == expected_score
            and match.first_leg_winner == expected_first_leg_winner
            and match.first_180_player == expected_first_180_player
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

    def _ensure_canonical_player_mappings(
        self,
        *,
        db,
        provider: str,
        fixtures: Iterable[CanonicalFixture],
    ) -> None:
        for fixture in fixtures:
            self._map_player_external_id(
                db=db,
                provider=provider,
                external_id=fixture.player_a_external_id,
                player_name=fixture.player_a_name,
                competition_code=fixture.competition_code.value,
            )
            self._map_player_external_id(
                db=db,
                provider=provider,
                external_id=fixture.player_b_external_id,
                player_name=fixture.player_b_name,
                competition_code=fixture.competition_code.value,
            )

    @staticmethod
    def _map_player_external_id(
        *,
        db,
        provider: str,
        external_id: str,
        player_name: str,
        competition_code: str,
    ) -> None:
        player = resolve_player_by_name(
            db,
            player_name,
            provider=provider,
        )

        if player is None:
            raise ValueError(
                f"Canonical player was not created: {player_name}."
            )

        map_entity(
            db,
            provider,
            "player",
            external_id,
            player.id,
            competition_code,
        )

    @staticmethod
    def _find_match(
        *,
        db,
        provider: str,
        match_external_id: str,
    ) -> Optional[Match]:
        mapping = (
            db.query(ProviderEntityMapping)
            .filter_by(
                provider=provider,
                entity_type="fixture",
                external_id=match_external_id,
            )
            .first()
        )

        if mapping is None:
            return None

        return (
            db.query(Match)
            .filter(Match.id == mapping.internal_id)
            .first()
        )

    @staticmethod
    def _player_name_for_external_id(
        *,
        db,
        provider: str,
        external_id: str,
        fallback: str,
    ) -> str:
        mapping = (
            db.query(ProviderEntityMapping)
            .filter_by(
                provider=provider,
                entity_type="player",
                external_id=external_id,
            )
            .first()
        )

        if mapping is None:
            return fallback

        player = (
            db.query(Player)
            .filter(Player.id == mapping.internal_id)
            .first()
        )

        return player.name if player else fallback

    @staticmethod
    def _participant_name(
        *,
        external_id: str,
        result: CanonicalMatchResult,
        player_a_name: str,
        player_b_name: str,
    ) -> str:
        if external_id == result.player_a_external_id:
            return player_a_name

        if external_id == result.player_b_external_id:
            return player_b_name

        raise ValueError(
            "Result participant identifier does not match either player."
        )

    def _optional_participant_name(
        self,
        *,
        external_id: Optional[str],
        result: CanonicalMatchResult,
        player_a_name: str,
        player_b_name: str,
    ) -> Optional[str]:
        if external_id is None:
            return None

        return self._participant_name(
            external_id=external_id,
            result=result,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
        )

    @staticmethod
    def _records(
        preview: CollectorFolderPreview,
        entity_type: str,
    ) -> list:
        mapping = preview.mappings.get(entity_type)

        if mapping is None:
            return []

        return list(mapping.records)

    @staticmethod
    def _fixture_to_historical_row(
        fixture: CanonicalFixture,
    ) -> dict:
        return {
            "external_id": fixture.external_id,
            "date": fixture.scheduled_at.date(),
            "competition": fixture.competition_code.value,
            "tournament": fixture.competition_name,
            "stage": fixture.stage or "Scheduled",
            "match_format": fixture.match_format,
            "status": fixture.status.value,
            "player_a": fixture.player_a_name,
            "player_b": fixture.player_b_name,
            "winner": None,
            "score": None,
            "first_180_player": None,
            "first_leg_winner": None,
            "provider": fixture.source.provider,
            "player_a_stats": {
                "one80s": 0,
                "average": 0.0,
                "checkout": 0.0,
                "first9_average": 0.0,
                "highest_checkout": 0,
            },
            "player_b_stats": {
                "one80s": 0,
                "average": 0.0,
                "checkout": 0.0,
                "first9_average": 0.0,
                "highest_checkout": 0,
            },
        }

    @staticmethod
    def _competition_code(
        fixtures: List[CanonicalFixture],
    ) -> str:
        competition_codes = {
            fixture.competition_code.value
            for fixture in fixtures
        }

        if len(competition_codes) == 1:
            return next(iter(competition_codes))

        return "OTHER"

    @staticmethod
    def _create_batch(
        *,
        db,
        preview: CollectorFolderPreview,
        filename: Optional[str],
        received_rows: int,
    ) -> HistoricalImportBatch:
        batch = HistoricalImportBatch(
            batch_uuid=str(uuid.uuid4()),
            filename=filename or CollectorCommitBridge._default_filename(
                preview,
                suffix="results",
            ),
            provider=preview.provider,
            competition_code="OTHER",
            status="importing",
            received_rows=received_rows,
            created_matches=0,
            duplicate_matches=0,
            rejected_rows=0,
            created_players=0,
            created_at=datetime.utcnow(),
        )

        db.add(batch)
        db.flush()

        return batch

    @staticmethod
    def _default_filename(
        preview: CollectorFolderPreview,
        *,
        suffix: str,
    ) -> str:
        folder_name = Path(preview.folder).name or "collector"
        return f"{folder_name}-{suffix}.csv"
