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


# Fitted on the historical development period ending
# 2026-03-13 and validated once against the sealed date-disjoint
# holdout beginning 2026-03-14.
#
# Sealed holdout results for the 90/10, scale-14 leg model:
# Handicap -1.5:
#   raw Brier        0.206148
#   calibrated Brier 0.208617
#   constant Brier   0.229120
#
# Total Legs Over 5.5:
#   raw Brier        0.245752
#   calibrated Brier 0.245944
#   constant Brier   0.247505

HANDICAP_CALIBRATION = PlattCalibration(
    slope=0.425,
    intercept=-0.35,
)

TOTAL_LEGS_CALIBRATION = PlattCalibration(
    slope=0.35,
    intercept=0.275,
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
