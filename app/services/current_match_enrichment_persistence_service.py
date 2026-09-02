from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.collector.result_committer import ResultCommitter
from app.collector.commit_helpers import find_match_by_external_id
from app.collector.statistics_committer import StatisticsCommitter
from app.models.historical_import import HistoricalImportBatch
from app.services.paper_trade_service import (
    settle_open_trades_for_fixture,
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
    Atomically persist a canonical current-match result and its two statistics
    records.

    ResultCommitter owns the scheduled -> completed transition and writes the
    winner/score. StatisticsCommitter owns immutable performance storage.
    Transaction ownership belongs to this service.
    """

    def __init__(
        self,
        *,
        statistics_committer: StatisticsCommitter | None = None,
        result_committer: ResultCommitter | None = None,
    ) -> None:
        self.statistics_committer = (
            statistics_committer or StatisticsCommitter()
        )
        self.result_committer = (
            result_committer or ResultCommitter()
        )

    def persist(
        self,
        db,
        result: CurrentMatchEnrichmentStatisticsResult,
    ) -> CurrentMatchEnrichmentPersistenceResult:
        if result.status != "canonicalized":
            raise ValueError(
                "Only canonicalized enrichment data can be persisted."
            )

        statistics = tuple(result.statistics)
        if len(statistics) != 2:
            raise ValueError(
                "Current-match enrichment must contain exactly "
                "two player statistics records."
            )

        canonical_result = result.result
        if canonical_result is None:
            raise ValueError(
                "Current-match enrichment cannot be persisted without "
                "a canonical match result."
            )

        expected_match_external_id = result.match_external_id
        if canonical_result.match_external_id != expected_match_external_id:
            raise ValueError(
                "Canonical result contains an inconsistent match external ID."
            )

        if canonical_result.source.provider != PROVIDER:
            raise ValueError(
                "Canonical result must originate from modus-official."
            )

        for record in statistics:
            if record.match_external_id != expected_match_external_id:
                raise ValueError(
                    "Canonical statistics contain inconsistent "
                    "match external IDs."
                )
            if record.source.provider != PROVIDER:
                raise ValueError(
                    "Canonical statistics must originate from "
                    "modus-official."
                )

        received_rows = 1 + len(statistics)
        batch = HistoricalImportBatch(
            batch_uuid=str(uuid.uuid4()),
            filename=(
                "current-match-enrichment-"
                f"{result.modus_match_id}.canonical"
            ),
            provider=PROVIDER,
            competition_code=COMPETITION_CODE,
            received_rows=received_rows,
            status="importing",
        )

        try:
            db.add(batch)
            db.flush()

            # Result first: this is the only operation allowed to promote the
            # fixture to completed and it also writes winner + score.
            self.result_committer.commit(
                db=db,
                provider=PROVIDER,
                results=(canonical_result,),
                batch=batch,
            )

            self.statistics_committer.commit(
                db=db,
                provider=PROVIDER,
                statistics=statistics,
                batch=batch,
            )

            match = find_match_by_external_id(
                db=db,
                provider=PROVIDER,
                match_external_id=expected_match_external_id,
            )
            if match is None:
                raise ValueError(
                    "Canonical fixture mapping disappeared before "
                    "paper-trade settlement."
                )

            settle_open_trades_for_fixture(
                db,
                match.id,
            )

            batch.received_rows = received_rows
            rejected_rows = int(batch.rejected_rows or 0)

            if rejected_rows:
                batch.status = "rejected"
                db.rollback()
                raise ValueError(
                    "Current-match enrichment persistence rejected "
                    f"{rejected_rows} canonical record(s). "
                    "No enrichment data was committed."
                )

            batch.status = "imported"
            db.commit()
            db.refresh(batch)

            return CurrentMatchEnrichmentPersistenceResult(
                internal_match_id=int(result.internal_match_id),
                modus_match_id=int(result.modus_match_id),
                batch_id=int(batch.id),
                batch_uuid=str(batch.batch_uuid),
                received_rows=int(batch.received_rows or 0),
                rejected_rows=int(batch.rejected_rows or 0),
                status="persisted",
                message=(
                    "Current MODUS match result and statistics were "
                    "persisted atomically through the canonical commit "
                    "pipeline."
                ),
            )
        except Exception:
            rollback = getattr(db, "rollback", None)
            if callable(rollback):
                rollback()
            raise
