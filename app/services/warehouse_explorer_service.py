from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.canonical_data import (
    DataProvenance,
    ProviderEntityMapping,
    RawIngestionRecord,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
    HistoricalImportPreview,
)
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.models.player import Player


@dataclass(frozen=True)
class WarehouseEntityRecord:
    item: HistoricalImportItem
    match: Optional[Match] = None
    player: Optional[Player] = None
    statistic: Optional[MatchPlayerStats] = None


@dataclass(frozen=True)
class WarehouseBatchDetail:
    batch: HistoricalImportBatch
    items: List[WarehouseEntityRecord]
    previews: List[HistoricalImportPreview]
    mappings: List[ProviderEntityMapping]
    provenance: List[DataProvenance]
    raw_records: List[RawIngestionRecord]

    @property
    def created_count(self) -> int:
        return sum(1 for record in self.items if record.item.action == "created")

    @property
    def updated_count(self) -> int:
        return sum(1 for record in self.items if record.item.action == "updated")

    @property
    def duplicate_count(self) -> int:
        return sum(1 for record in self.items if record.item.action == "duplicate")

    @property
    def rejected_count(self) -> int:
        return sum(1 for record in self.items if record.item.action == "rejected")


class WarehouseExplorerService:
    """Read-only inspection of committed import batches and linked records."""

    def list_batches(
        self,
        db: Session,
        *,
        limit: int = 100,
    ) -> List[HistoricalImportBatch]:
        return (
            db.query(HistoricalImportBatch)
            .order_by(HistoricalImportBatch.id.desc())
            .limit(limit)
            .all()
        )

    def batch_detail(
        self,
        db: Session,
        batch_id: int,
    ) -> Optional[WarehouseBatchDetail]:
        batch = (
            db.query(HistoricalImportBatch)
            .filter(HistoricalImportBatch.id == batch_id)
            .first()
        )
        if batch is None:
            return None

        items = (
            db.query(HistoricalImportItem)
            .filter(HistoricalImportItem.batch_id == batch.id)
            .order_by(HistoricalImportItem.id)
            .all()
        )

        records = [
            self._record_for_item(db, item)
            for item in items
        ]

        previews = (
            db.query(HistoricalImportPreview)
            .filter(HistoricalImportPreview.batch_id == batch.id)
            .order_by(HistoricalImportPreview.id)
            .all()
        )

        external_ids = {
            item.external_id
            for item in items
            if item.external_id
        }
        internal_ids = {
            item.internal_id
            for item in items
            if item.internal_id is not None
        }

        mappings_query = db.query(ProviderEntityMapping).filter(
            ProviderEntityMapping.provider == batch.provider
        )
        if external_ids:
            mappings_query = mappings_query.filter(
                ProviderEntityMapping.external_id.in_(external_ids)
            )
            mappings = mappings_query.order_by(
                ProviderEntityMapping.entity_type,
                ProviderEntityMapping.external_id,
            ).all()
        else:
            mappings = []

        if internal_ids:
            provenance = (
                db.query(DataProvenance)
                .filter(DataProvenance.internal_id.in_(internal_ids))
                .order_by(
                    DataProvenance.entity_type,
                    DataProvenance.internal_id,
                    DataProvenance.field_name,
                )
                .all()
            )
        else:
            provenance = []

        if external_ids:
            raw_records = (
                db.query(RawIngestionRecord)
                .filter(
                    RawIngestionRecord.provider == batch.provider,
                    RawIngestionRecord.external_id.in_(external_ids),
                )
                .order_by(RawIngestionRecord.id)
                .all()
            )
        else:
            raw_records = []

        return WarehouseBatchDetail(
            batch=batch,
            items=records,
            previews=previews,
            mappings=mappings,
            provenance=provenance,
            raw_records=raw_records,
        )

    @staticmethod
    def _record_for_item(
        db: Session,
        item: HistoricalImportItem,
    ) -> WarehouseEntityRecord:
        match = None
        player = None
        statistic = None

        if item.internal_id is not None:
            if item.entity_type in {"match", "fixture", "result"}:
                match = (
                    db.query(Match)
                    .filter(Match.id == item.internal_id)
                    .first()
                )
            elif item.entity_type == "player":
                player = (
                    db.query(Player)
                    .filter(Player.id == item.internal_id)
                    .first()
                )
            elif item.entity_type in {"statistics", "statistic"}:
                statistic = (
                    db.query(MatchPlayerStats)
                    .filter(MatchPlayerStats.id == item.internal_id)
                    .first()
                )

        return WarehouseEntityRecord(
            item=item,
            match=match,
            player=player,
            statistic=statistic,
        )
