from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.services.prediction_feature_plugin import FeatureContribution


@dataclass(frozen=True)
class NumericEdgeFeature:
    name: str
    weight: float
    scale: float
    edge_getter: Callable
    label: str

    def score(self, snapshot) -> FeatureContribution:
        raw_edge = float(self.edge_getter(snapshot))
        normalised = min(max(raw_edge / self.scale, -1.0), 1.0)
        weighted = normalised * self.weight

        if weighted > 0:
            favoured = snapshot.player_a.player_name
        elif weighted < 0:
            favoured = snapshot.player_b.player_name
        else:
            favoured = None

        explanation = (
            f"{favoured} has the stronger {self.label}."
            if favoured
            else f"The players are level on {self.label}."
        )

        return FeatureContribution(
            feature_name=self.name,
            raw_edge=round(raw_edge, 6),
            normalised_edge=round(normalised, 6),
            weight=round(self.weight, 6),
            weighted_score=round(weighted, 6),
            confidence=100.0,
            explanation=explanation,
        )


def _trend_change(player, metric: str) -> float:
    for trend in player.advanced_features.trends:
        if trend.metric == metric:
            return float(trend.absolute_change or 0.0)
    return 0.0


def default_transparent_v3_features():
    return (
        NumericEdgeFeature(
            "overall_strength", 0.24, 160.0,
            lambda s: s.player_a.overall_rating - s.player_b.overall_rating,
            "overall strength",
        ),
        NumericEdgeFeature(
            "recent_form", 0.18, 160.0,
            lambda s: s.player_a.form_rating - s.player_b.form_rating,
            "recent form",
        ),
        NumericEdgeFeature(
            "scoring_power", 0.15, 160.0,
            lambda s: s.player_a.scoring_rating - s.player_b.scoring_rating,
            "scoring power",
        ),
        NumericEdgeFeature(
            "finishing_strength", 0.12, 160.0,
            lambda s: s.player_a.finishing_rating - s.player_b.finishing_rating,
            "finishing strength",
        ),
        NumericEdgeFeature(
            "maximums_strength", 0.08, 160.0,
            lambda s: s.player_a.maximums_rating - s.player_b.maximums_rating,
            "maximum scoring",
        ),
        NumericEdgeFeature(
            "recent_win_rate", 0.10, 50.0,
            lambda s: (
                (s.player_a.advanced_features.windows["last_5"].win_percentage or 0.0)
                - (s.player_b.advanced_features.windows["last_5"].win_percentage or 0.0)
            ),
            "last-five win rate",
        ),
        NumericEdgeFeature(
            "checkout_trend", 0.07, 20.0,
            lambda s: (
                _trend_change(s.player_a, "checkout_percentage")
                - _trend_change(s.player_b, "checkout_percentage")
            ),
            "checkout trend",
        ),
        NumericEdgeFeature(
            "deciding_strength", 0.06, 50.0,
            lambda s: (
                (s.player_a.advanced_features.windows["last_20"].deciding_win_percentage or 50.0)
                - (s.player_b.advanced_features.windows["last_20"].deciding_win_percentage or 50.0)
            ),
            "deciding-match record",
        ),
    )


def transparent_v32_features():
    """
    Transparent v3.1 features plus recent scoring consistency.

    Lower recent three-dart-average variation is treated as better.
    Recent form remains installed with its evidence-backed zero weight.
    """
    from dataclasses import replace

    features = [
        replace(feature, weight=0.0)
        if feature.name == "recent_form"
        else feature
        for feature in default_transparent_v3_features()
    ]

    features.append(
        NumericEdgeFeature(
            name="scoring_consistency",
            weight=0.05,
            scale=8.0,
            edge_getter=lambda snapshot: (
                _consistency_value(
                    snapshot.player_b
                )
                - _consistency_value(
                    snapshot.player_a
                )
            ),
            label="recent scoring consistency",
        )
    )

    return tuple(features)


def _consistency_value(player) -> float:
    consistency = getattr(
        player.advanced_features,
        "consistency",
        None,
    )

    if consistency is None:
        return 0.0

    value = (
        consistency
        .three_dart_average_stddev
    )

    return (
        float(value)
        if value is not None
        else 0.0
    )
