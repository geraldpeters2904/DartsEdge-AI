from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import List

from app.models.canonical_data import ProviderEntityMapping
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.schemas.canonical import CanonicalFixture
from app.services.canonical_data_service import (
    map_entity,
    record_provenance,
    store_raw,
)
from app.services.historical_import_service import _resolve_player


class FixtureCommitter:
    """
    Commit canonical fixtures by stable provider external ID.

    Scheduled fixtures create players, a Match, provider mappings, raw records
    and provenance. They do not create placeholder MatchPlayerStats rows.
    Repeated fixtures are duplicate-safe, while changed fixtures update the
    existing Match referenced by the provider mapping.
    """

    def commit(
        self,
        *,
        db,
        provider: str,
        filename: str,
        competition: str,
        fixtures: List[CanonicalFixture],
    ) -> HistoricalImportBatch:
        batch = HistoricalImportBatch(
            batch_uuid=str(uuid.uuid4()),
            filename=filename,
            provider=provider,
            competition_code=competition,
            received_rows=len(fixtures),
            status="importing",
        )
        db.add(batch)
        db.flush()

        created_players = 0
        created_matches = 0
        duplicates = 0
        rejected = 0

        try:
            for fixture in fixtures:
                try:
                    action = self._commit_one(
                        db=db,
                        provider=provider,
                        fixture=fixture,
                        batch=batch,
                    )
                    created_players += action["created_players"]
                    created_matches += int(action["action"] == "created")
                    duplicates += int(action["action"] == "duplicate")
                except Exception as exc:
                    rejected += 1
                    db.add(
                        HistoricalImportItem(
                            batch_id=batch.id,
                            entity_type="fixture",
                            external_id=fixture.external_id,
                            action="rejected",
                            detail=str(exc),
                            created_by_batch=False,
                        )
                    )

            batch.created_players = created_players
            batch.created_matches = created_matches
            batch.duplicate_matches = duplicates
            batch.rejected_rows = rejected
            batch.status = "imported"

            db.commit()
            db.refresh(batch)
            return batch
        except Exception:
            db.rollback()
            raise

    def _commit_one(
        self,
        *,
        db,
        provider: str,
        fixture: CanonicalFixture,
        batch: HistoricalImportBatch,
    ) -> dict:
        raw_record, _ = store_raw(
            db,
            provider,
            "fixture",
            fixture.external_id,
            fixture.model_dump(mode="json"),
        )

        player_a, created_a = _resolve_player(
            db,
            fixture.player_a_name,
            provider,
            batch,
        )
        player_b, created_b = _resolve_player(
            db,
            fixture.player_b_name,
            provider,
            batch,
        )

        competition_code = fixture.competition_code.value

        map_entity(
            db,
            provider,
            "player",
            fixture.player_a_external_id,
            player_a.id,
            competition_code,
        )
        map_entity(
            db,
            provider,
            "player",
            fixture.player_b_external_id,
            player_b.id,
            competition_code,
        )

        mapping = (
            db.query(ProviderEntityMapping)
            .filter_by(
                provider=provider,
                entity_type="fixture",
                external_id=fixture.external_id,
            )
            .first()
        )

        incoming = self._fixture_state(fixture)

        if mapping is not None:
            match = (
                db.query(Match)
                .filter(Match.id == mapping.internal_id)
                .first()
            )
            if match is None:
                raise ValueError(
                    "Fixture mapping points to a missing internal match."
                )

            if (
                match.status == "completed"
                and fixture.status.value != "completed"
            ):
                raw_record.processed = True
                db.add(
                    HistoricalImportItem(
                        batch_id=batch.id,
                        entity_type="fixture",
                        internal_id=match.id,
                        external_id=fixture.external_id,
                        action="duplicate",
                        detail=(
                            "Ignored an older scheduled fixture because the "
                            "warehouse match is already completed."
                        ),
                        created_by_batch=False,
                    )
                )
                return {
                    "action": "duplicate",
                    "created_players": int(created_a) + int(created_b),
                }

            current = self._match_state(match)
            if current == incoming:
                raw_record.processed = True
                db.add(
                    HistoricalImportItem(
                        batch_id=batch.id,
                        entity_type="fixture",
                        internal_id=match.id,
                        external_id=fixture.external_id,
                        action="duplicate",
                        detail="Fixture already contains identical values.",
                        created_by_batch=False,
                    )
                )
                return {
                    "action": "duplicate",
                    "created_players": int(created_a) + int(created_b),
                }

            previous = current
            self._apply_fixture(match, fixture)
            db.flush()

            self._record_fixture_provenance(
                db=db,
                provider=provider,
                fixture=fixture,
                match=match,
            )

            raw_record.processed = True
            db.add(
                HistoricalImportItem(
                    batch_id=batch.id,
                    entity_type="fixture",
                    internal_id=match.id,
                    external_id=fixture.external_id,
                    action="updated",
                    detail=json.dumps(
                        {
                            "previous": previous,
                            "current": self._match_state(match),
                        },
                        sort_keys=True,
                    ),
                    created_by_batch=False,
                )
            )
            return {
                "action": "updated",
                "created_players": int(created_a) + int(created_b),
            }

        match = Match()
        self._apply_fixture(match, fixture)
        db.add(match)
        db.flush()

        map_entity(
            db,
            provider,
            "fixture",
            fixture.external_id,
            match.id,
            competition_code,
        )

        self._record_fixture_provenance(
            db=db,
            provider=provider,
            fixture=fixture,
            match=match,
        )

        raw_record.processed = True
        db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="match",
                internal_id=match.id,
                external_id=fixture.external_id,
                action="created",
                created_by_batch=True,
            )
        )

        return {
            "action": "created",
            "created_players": int(created_a) + int(created_b),
        }

    @staticmethod
    def _apply_fixture(match: Match, fixture: CanonicalFixture) -> None:
        match.date = fixture.scheduled_at.date()
        match.tournament = fixture.competition_name
        match.stage = fixture.stage or fixture.group or "Scheduled"
        match.match_format = fixture.match_format
        match.status = fixture.status.value
        match.player_a = fixture.player_a_name
        match.player_b = fixture.player_b_name

        if fixture.status.value != "completed":
            match.winner = None
            match.score = None
            match.first_180_player = None
            match.first_leg_winner = None

    @staticmethod
    def _fixture_state(fixture: CanonicalFixture) -> dict:
        return {
            "date": fixture.scheduled_at.date().isoformat(),
            "tournament": fixture.competition_name,
            "stage": fixture.stage or fixture.group or "Scheduled",
            "match_format": fixture.match_format,
            "status": fixture.status.value,
            "player_a": fixture.player_a_name,
            "player_b": fixture.player_b_name,
        }

    @staticmethod
    def _match_state(match: Match) -> dict:
        return {
            "date": match.date.isoformat() if match.date else None,
            "tournament": match.tournament,
            "stage": match.stage,
            "match_format": match.match_format,
            "status": match.status,
            "player_a": match.player_a,
            "player_b": match.player_b,
        }

    @staticmethod
    def _record_fixture_provenance(
        *,
        db,
        provider: str,
        fixture: CanonicalFixture,
        match: Match,
    ) -> None:
        for field_name in (
            "date",
            "tournament",
            "stage",
            "match_format",
            "status",
            "player_a",
            "player_b",
        ):
            record_provenance(
                db,
                "fixture",
                match.id,
                field_name,
                provider,
                fixture.external_id,
                confidence=fixture.source.confidence.value,
            )
