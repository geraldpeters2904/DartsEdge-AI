from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FeatureContribution:
    feature_name: str
    raw_edge: float
    normalised_edge: float
    weight: float
    weighted_score: float
    confidence: float
    explanation: str


class PredictionFeature(Protocol):
    name: str
    weight: float

    def score(self, snapshot) -> FeatureContribution:
        ...
