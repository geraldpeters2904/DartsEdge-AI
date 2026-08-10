from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.collector.statistics_committer import StatisticsCommitter
from app.models.historical_import import (
    HistoricalImportBatch,
)
from app.services.current_match_enrichment_statistics_service import (
    CurrentMatchEnrichmentStatisticsResult,
)


PROVIDER = "modus-official"
COMPETITION_CODE = "MODUS"


@dataclass(frozen=True)
class CurrentMatchEnrichmentPersistenceResult:
    internal_match_id: int
    modus_match_id: int
    batch_id: int
    batch_uuid: str
    received_rows: int
    rejected_rows: int
    status: str
    message: str


class CurrentMatchEnrichmentPersistenceService:
    """
    Persist canonical current-match statistics through StatisticsCommitter.

    Transaction ownership belongs to this service. StatisticsCommitter
    remains responsible for immutable performance storage, raw records,
    mappings, provenance and duplicate detection.
    """

    def __init__(
        self,
        *,
        statistics_committer: StatisticsCommitter | None = None,
    ) -> None:
        self.statistics_committer = (
            statistics_committer or StatisticsCommitter()
        )

    def persist(
        self,
        db,
        result: CurrentMatchEnrichmentStatisticsResult,
    ) -> CurrentMatchEnrichmentPersistenceResult:
        if result.status != "canonicalized":
            raise ValueError(
                "Only canonicalized enrichment statistics "
                "can be persisted."
            )

        statistics = tuple(result.statistics)

        if len(statistics) != 2:
            raise ValueError(
                "Current-match enrichment must contain exactly "
                "two player statistics records."
            )

        expected_match_external_id = (
            result.match_external_id
        )

        for record in statistics:
            if (
                record.match_external_id
                != expected_match_external_id
            ):
                raise ValueError(
                    "Canonical statistics contain inconsistent "
                    "match external IDs."
                )

            if record.source.provider != PROVIDER:
                raise ValueError(
                    "Canonical statistics must originate from "
                    "modus-official."
                )

        batch = HistoricalImportBatch(
            batch_uuid=str(uuid.uuid4()),
            filename=(
                "current-match-enrichment-"
                f"{result.modus_match_id}.canonical"
            ),
            provider=PROVIDER,
            competition_code=COMPETITION_CODE,
            received_rows=len(statistics),
            status="importing",
        )

        try:
            db.add(batch)
            db.flush()

            self.statistics_committer.commit(
                db=db,
                provider=PROVIDER,
                statistics=statistics,
                batch=batch,
            )

            batch.received_rows = len(statistics)

            rejected_rows = int(
                batch.rejected_rows or 0
            )

            if rejected_rows:
                batch.status = "rejected"
                db.rollback()

                raise ValueError(
                    "Current-match enrichment persistence "
                    f"rejected {rejected_rows} statistics "
                    "record(s). No enrichment data was committed."
                )

            batch.status = "imported"

            db.commit()
            db.refresh(batch)

            return CurrentMatchEnrichmentPersistenceResult(
                internal_match_id=int(
                    result.internal_match_id
                ),
                modus_match_id=int(
                    result.modus_match_id
                ),
                batch_id=int(batch.id),
                batch_uuid=str(batch.batch_uuid),
                received_rows=int(
                    batch.received_rows or 0
                ),
                rejected_rows=int(
                    batch.rejected_rows or 0
                ),
                status="persisted",
                message=(
                    "Current MODUS match statistics were "
                    "persisted through the immutable statistics "
                    "commit pipeline."
                ),
            )

        except Exception:
            rollback = getattr(
                db,
                "rollback",
                None,
            )

            if callable(rollback):
                rollback()

            raise
