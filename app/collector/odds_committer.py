from __future__ import annotations

import hashlib
import json
from typing import Iterable, Optional

from app.collector.commit_helpers import (
    find_match_by_external_id,
)
from app.models.canonical_data import (
    ProviderEntityMapping,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.odds_snapshot import OddsSnapshot
from app.models.player import Player
from app.schemas.canonical import CanonicalOddsSnapshot
from app.services.canonical_data_service import (
    map_entity,
    record_provenance,
    store_raw,
)


class OddsCommitter:
    """
    Store immutable bookmaker-price observations.

    Every distinct observed price is retained. An exact repeat of the
    same fixture, market, selection, bookmaker, capture time and price
    is treated as a duplicate.
    """

    def commit(
        self,
        *,
        db,
        provider: str,
        odds: Iterable[CanonicalOddsSnapshot],
        batch: HistoricalImportBatch,
    ) -> None:
        rejected = 0

        for record in odds:
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
                        entity_type="odds",
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
        record: CanonicalOddsSnapshot,
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

        selection_name = self._resolve_selection_name(
            db=db,
            provider=provider,
            record=record,
            match=match,
        )

        fingerprint = self._fingerprint(
            provider=provider,
            match_external_id=record.match_external_id,
            market=record.market,
            selection_name=selection_name,
            bookmaker=record.bookmaker,
            decimal_odds=record.decimal_odds,
            captured_at=record.captured_at,
        )

        raw_record, _ = store_raw(
            db,
            provider,
            "odds",
            record.source.external_id,
            record.model_dump(mode="json"),
        )

        existing = (
            db.query(OddsSnapshot)
            .filter_by(fingerprint=fingerprint)
            .first()
        )

        if existing is not None:
            raw_record.processed = True

            db.add(
                HistoricalImportItem(
                    batch_id=batch.id,
                    entity_type="odds_snapshot",
                    internal_id=existing.id,
                    external_id=record.source.external_id,
                    action="duplicate",
                    detail="Identical odds snapshot already exists.",
                    created_by_batch=False,
                )
            )
            return

        if match.date is None:
            raise ValueError(
                f"Fixture {record.match_external_id} has no date."
            )

        snapshot = OddsSnapshot(
            fixture_date=match.date,
            tournament=match.tournament or "Unknown",
            player_a=match.player_a,
            player_b=match.player_b,
            market=record.market,
            selection=selection_name,
            bookmaker=record.bookmaker,
            decimal_odds=record.decimal_odds,
            captured_at=record.captured_at,
            provider_id=record.source.provider,
            external_id=record.source.external_id,
            fingerprint=fingerprint,
        )

        db.add(snapshot)
        db.flush()

        map_entity(
            db,
            provider,
            "odds",
            record.source.external_id,
            snapshot.id,
            record.source.competition_code,
        )

        for field_name in (
            "market",
            "selection",
            "bookmaker",
            "decimal_odds",
            "captured_at",
        ):
            record_provenance(
                db,
                "odds",
                snapshot.id,
                field_name,
                provider,
                record.source.external_id,
                confidence=record.source.confidence.value,
            )

        raw_record.processed = True

        db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="odds_snapshot",
                internal_id=snapshot.id,
                external_id=record.source.external_id,
                action="created",
                detail=json.dumps(
                    {
                        "match_external_id": (
                            record.match_external_id
                        ),
                        "market": record.market,
                        "selection": selection_name,
                        "bookmaker": record.bookmaker,
                        "decimal_odds": record.decimal_odds,
                        "captured_at": (
                            record.captured_at.isoformat()
                        ),
                    },
                    sort_keys=True,
                ),
                created_by_batch=True,
            )
        )

    def _resolve_selection_name(
        self,
        *,
        db,
        provider: str,
        record: CanonicalOddsSnapshot,
        match,
    ) -> str:
        selection_name = record.selection_name.strip()

        if record.market != "match_winner":
            return selection_name

        if record.selection_external_id:
            player = self._find_player(
                db=db,
                provider=provider,
                external_id=record.selection_external_id,
            )

            if player is None:
                raise ValueError(
                    "No player mapping was found for odds selection "
                    f"{record.selection_external_id}."
                )

            selection_name = player.name

        participants = {
            match.player_a,
            match.player_b,
        }

        if selection_name not in participants:
            raise ValueError(
                "Match-winner selection is not a participant in "
                f"fixture {record.match_external_id}: "
                f"{selection_name}."
            )

        return selection_name

    @staticmethod
    def _find_player(
        *,
        db,
        provider: str,
        external_id: str,
    ) -> Optional[Player]:
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
            return None

        return (
            db.query(Player)
            .filter(Player.id == mapping.internal_id)
            .first()
        )

    @staticmethod
    def _fingerprint(
        *,
        provider: str,
        match_external_id: str,
        market: str,
        selection_name: str,
        bookmaker: str,
        decimal_odds: float,
        captured_at,
    ) -> str:
        canonical = "|".join(
            (
                provider.strip().lower(),
                match_external_id.strip(),
                market.strip().lower(),
                selection_name.strip().lower(),
                bookmaker.strip().lower(),
                format(float(decimal_odds), ".10g"),
                captured_at.isoformat(),
            )
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()
