from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PlattCalibration:
    """
    Logistic calibration applied to an existing model probability.

    The input probability is converted to log-odds, transformed using
    fitted slope/intercept parameters, and converted back to probability.
    """

    slope: float
    intercept: float
    epsilon: float = 1e-6

    def apply(self, probability: float) -> float:
        probability = float(probability)

        if probability < 0.0 or probability > 1.0:
            raise ValueError(
                "probability must be between 0 and 1."
            )

        clipped = min(
            max(probability, self.epsilon),
            1.0 - self.epsilon,
        )

        log_odds = math.log(
            clipped / (1.0 - clipped)
        )

        calibrated_log_odds = (
            self.slope * log_odds
            + self.intercept
        )

        if calibrated_log_odds >= 0.0:
            z = math.exp(-calibrated_log_odds)
            return 1.0 / (1.0 + z)

        z = math.exp(calibrated_log_odds)
        return z / (1.0 + z)


# Fitted on the chronological historical training period ending
# 2025-09-26 and validated against the date-disjoint holdout
# beginning 2025-09-27.
#
# Holdout results:
# Handicap -1.5:
#   raw Brier        0.237586
#   calibrated Brier 0.211123
#   constant Brier   0.226523
#
# Total Legs Over 5.5:
#   raw Brier        0.262687
#   calibrated Brier 0.243754
#   constant Brier   0.245379

HANDICAP_CALIBRATION = PlattCalibration(
    slope=0.225,
    intercept=-0.45,
)

TOTAL_LEGS_CALIBRATION = PlattCalibration(
    slope=0.15,
    intercept=0.375,
)


def calibrate_handicap_probability(
    probability: float,
) -> float:
    return HANDICAP_CALIBRATION.apply(
        probability
    )


def calibrate_total_legs_probability(
    probability: float,
) -> float:
    return TOTAL_LEGS_CALIBRATION.apply(
        probability
    )
