from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.cli_commands.benchmark import (
    register_benchmark_command,
)
from app.cli_commands.segments import (
    register_segments_command,
)
from app.cli_commands.contribution_v3 import (
    register_contribution_v3_command,
)
from app.cli_commands.optimise_weight_v3 import (
    register_optimise_weight_v3_command,
)
from app.cli_commands.consensus_weight_v3 import (
    register_consensus_weight_v3_command,
)
from app.cli_commands.tune_features_v32 import (
    register_tune_features_v32_command,
)
from app.services.model_performance_laboratory import (
    ModelPerformanceLaboratory,
)
from app.services.prediction_laboratory_service import (
    PredictionLaboratoryService,
)
from app.services.prediction_model_registry import (
    prediction_model_registry,
)


def _format_metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.3f}{suffix}"


def model_backtest_command(
    args,
    *,
    laboratory: Optional[
        ModelPerformanceLaboratory
    ] = None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or ModelPerformanceLaboratory()
    )

    db = session_factory()

    try:
        match_ids = None

        if args.limit is not None:
            from app.models.match import Match

            selection = (
                db.query(Match.id)
                .filter(
                    Match.status
                    == "completed"
                )
                .order_by(
                    Match.date.asc(),
                    Match.id.asc(),
                )
            )

            if args.offset:
                selection = selection.offset(
                    args.offset
                )

            match_ids = [
                match_id
                for (match_id,) in (
                    selection
                    .limit(args.limit)
                    .all()
                )
            ]

        summary = (
            laboratory.evaluate_model(
                db,
                model_name=args.model,
                match_ids=match_ids,
                competition_code=(
                    args.competition
                ),
            )
        )

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()

    print()
    print("=" * 68)
    print("DartsEdge Model Backtest")
    print("=" * 68)
    print(
        f"Model             : "
        f"{summary.model_name}"
    )
    print(
        f"Version           : "
        f"{summary.model_version}"
    )
    print(
        f"Considered        : "
        f"{summary.matches_considered}"
    )
    print(
        f"Evaluated         : "
        f"{summary.matches_evaluated}"
    )
    print(
        f"Skipped           : "
        f"{summary.matches_skipped}"
    )
    print(
        f"Correct           : "
        f"{summary.correct_predictions}"
    )
    print(
        "Accuracy          : "
        f"{_format_metric(summary.accuracy, suffix='%')}"
    )
    print(
        "Brier score       : "
        f"{_format_metric(summary.average_brier_score)}"
    )
    print(
        "Log loss          : "
        f"{_format_metric(summary.average_log_loss)}"
    )
    print(
        "Best confidence   : "
        f"{summary.best_confidence_band or '—'}"
    )
    print(
        "Best conf. acc.   : "
        f"{_format_metric(summary.best_confidence_accuracy, suffix='%')}"
    )
    print(
        "Weak confidence   : "
        f"{summary.weakest_confidence_band or '—'}"
    )
    print(
        "Weak conf. acc.   : "
        f"{_format_metric(summary.weakest_confidence_accuracy, suffix='%')}"
    )
    print(
        "Best tournament   : "
        f"{summary.best_tournament or '—'}"
    )
    print(
        "Weak tournament   : "
        f"{summary.weakest_tournament or '—'}"
    )
    print(
        "Best stage        : "
        f"{summary.best_stage or '—'}"
    )
    print(
        "Weak stage        : "
        f"{summary.weakest_stage or '—'}"
    )
    print("=" * 68)

    return 0


def model_compare_command(
    args,
    *,
    laboratory: Optional[
        ModelPerformanceLaboratory
    ] = None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or ModelPerformanceLaboratory()
    )
    db = session_factory()

    try:
        match_ids = None

        if (
            args.limit is not None
            or args.offset
        ):
            from app.models.match import Match

            selection = (
                db.query(Match.id)
                .filter(
                    Match.status
                    == "completed"
                )
                .order_by(
                    Match.date.asc(),
                    Match.id.asc(),
                )
            )

            if args.offset:
                selection = selection.offset(
                    args.offset
                )

            if args.limit is not None:
                selection = selection.limit(
                    args.limit
                )

            match_ids = [
                match_id
                for (match_id,) in selection.all()
            ]

        result = laboratory.compare_models(
            db,
            model_names=(
                args.models
                if args.models
                else None
            ),
            match_ids=match_ids,
            competition_code=(
                args.competition
            ),
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()

    print()
    print("=" * 68)
    print("DartsEdge Model Comparison")
    print("=" * 68)

    for summary in result.summaries:
        print(
            f"{summary.model_name:<18} "
            f"{summary.model_version:<22} "
            "accuracy="
            f"{_format_metric(summary.accuracy, suffix='%'):<10} "
            "brier="
            f"{_format_metric(summary.average_brier_score):<9} "
            "logloss="
            f"{_format_metric(summary.average_log_loss)}"
        )

    print()
    print(
        "Best model        : "
        f"{result.best_model_name or '—'}"
    )
    print(
        "Best version      : "
        f"{result.best_model_version or '—'}"
    )
    print(
        "Best accuracy     : "
        f"{_format_metric(result.best_accuracy, suffix='%')}"
    )
    print("=" * 68)

    return 0


def model_laboratory_command(
    args,
    *,
    laboratory: Optional[
        PredictionLaboratoryService
    ] = None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or PredictionLaboratoryService()
    )
    db = session_factory()

    try:
        if args.match is not None:
            report = laboratory.analyse_match(
                db,
                args.match,
                model_name=args.model,
                competition_code=(
                    args.competition
                ),
            )
        else:
            report = laboratory.compare_players(
                db,
                player_a_name=args.player_a,
                player_b_name=args.player_b,
                model_name=args.model,
                competition_code=(
                    args.competition
                ),
            )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()

    prediction = report.prediction
    snapshot = report.snapshot

    print()
    print("=" * 68)
    print("DartsEdge Prediction Laboratory")
    print("=" * 68)
    print(
        f"Model             : "
        f"{report.model_name}"
    )
    print(
        f"Version           : "
        f"{report.model_version}"
    )
    print(
        f"Player A          : "
        f"{prediction.player_a_name}"
    )
    print(
        f"Player B          : "
        f"{prediction.player_b_name}"
    )
    print(
        "Player A win      : "
        f"{prediction.player_a_probability:.3f}%"
    )
    print(
        "Player B win      : "
        f"{prediction.player_b_probability:.3f}%"
    )
    print(
        f"Predicted winner  : "
        f"{prediction.predicted_winner}"
    )
    print(
        f"Confidence        : "
        f"{prediction.confidence:.3f}%"
    )
    print()
    print(
        "Overall edge      : "
        f"{snapshot.overall_edge:+.3f}"
    )
    print(
        "Scoring edge      : "
        f"{snapshot.scoring_edge:+.3f}"
    )
    print(
        "Finishing edge    : "
        f"{snapshot.finishing_edge:+.3f}"
    )
    print(
        "Maximums edge     : "
        f"{snapshot.maximums_edge:+.3f}"
    )
    print(
        "Form edge         : "
        f"{snapshot.form_edge:+.3f}"
    )
    print(
        "Momentum edge     : "
        f"{_format_metric(snapshot.momentum_edge)}"
    )

    if report.strongest_factors:
        print()
        print("Strongest factors")

        for factor in (
            report.strongest_factors
        ):
            print(
                f"  • {factor.feature}: "
                f"{factor.favoured_player}"
            )

    if report.opposing_factors:
        print()
        print("Opposing factors")

        for factor in (
            report.opposing_factors
        ):
            print(
                f"  • {factor.feature}: "
                f"{factor.favoured_player}"
            )

    print("=" * 68)

    return 0


def register_model_commands(
    commands,
) -> None:
    model = commands.add_parser(
        "model",
        help=(
            "Prediction model analysis commands."
        ),
    )
    model_commands = model.add_subparsers(
        dest="model_command"
    )

    backtest = model_commands.add_parser(
        "backtest",
        help=(
            "Back-test one registered model."
        ),
    )
    backtest.add_argument(
        "--model",
        default=(
            prediction_model_registry
            .default_name
        ),
        help="Registered model name.",
    )
    backtest.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate N completed matches.",
    )
    backtest.add_argument(
        "--offset",
        type=int,
        default=0,
        help=(
            "Skip this many completed matches "
            "before evaluating."
        ),
    )
    backtest.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    backtest.set_defaults(
        func=model_backtest_command
    )

    compare = model_commands.add_parser(
        "compare",
        help=(
            "Compare registered prediction models."
        ),
    )
    compare.add_argument(
        "--models",
        nargs="*",
        default=None,
        help=(
            "Specific registered model names."
        ),
    )
    compare.add_argument(
        "--offset",
        type=int,
        default=0,
        help=(
            "Skip this many completed matches "
            "before comparison."
        ),
    )
    compare.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Compare models over N completed matches."
        ),
    )
    compare.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    compare.set_defaults(
        func=model_compare_command
    )

    laboratory = model_commands.add_parser(
        "laboratory",
        help=(
            "Explain one fixture or ad-hoc "
            "player comparison."
        ),
    )

    source = laboratory.add_mutually_exclusive_group(
        required=True
    )
    source.add_argument(
        "--match",
        type=int,
        help="Existing match ID.",
    )
    source.add_argument(
        "--player-a",
        help="First player name.",
    )

    laboratory.add_argument(
        "--player-b",
        help=(
            "Second player name. Required with "
            "--player-a."
        ),
    )
    laboratory.add_argument(
        "--model",
        default=(
            prediction_model_registry
            .default_name
        ),
        help="Registered model name.",
    )
    laboratory.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    laboratory.set_defaults(
        func=model_laboratory_command
    )

    register_benchmark_command(
        model_commands
    )
    register_segments_command(
        model_commands
    )
    register_contribution_v3_command(
        model_commands
    )
    register_optimise_weight_v3_command(
        model_commands
    )
    register_consensus_weight_v3_command(
        model_commands
    )
    register_tune_features_v32_command(
        model_commands
    )
