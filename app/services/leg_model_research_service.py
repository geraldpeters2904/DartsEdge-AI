from __future__ import annotations

import math


def candidate_leg_win_probability(
    *,
    average_a,
    checkout_a,
    average_b,
    checkout_b,
    average_weight,
    checkout_weight,
    logistic_scale,
):
    average_weight = float(average_weight)
    checkout_weight = float(checkout_weight)
    logistic_scale = float(logistic_scale)

    if logistic_scale <= 0.0:
        raise ValueError("logistic_scale must be positive.")

    score_a = (
        float(average_a) * average_weight
        + float(checkout_a) * checkout_weight
    )
    score_b = (
        float(average_b) * average_weight
        + float(checkout_b) * checkout_weight
    )

    return 1.0 / (
        1.0
        + math.exp(
            (score_b - score_a) / logistic_scale
        )
    )


def candidate_market_probabilities(
    record,
    *,
    average_weight,
    checkout_weight,
    logistic_scale,
    handicap_line=-1.5,
    total_legs_line=5.5,
):
    from types import SimpleNamespace

    from app.services.simulation_service import (
        handicap_cover_probability,
        simulate_match,
        total_legs_over_probability,
    )

    leg_probability = candidate_leg_win_probability(
        average_a=record.player_a_average,
        checkout_a=record.player_a_checkout,
        average_b=record.player_b_average,
        checkout_b=record.player_b_checkout,
        average_weight=average_weight,
        checkout_weight=checkout_weight,
        logistic_scale=logistic_scale,
    )

    profile_a = SimpleNamespace(
        average=float(record.player_a_average),
        checkout=float(record.player_a_checkout),
    )
    profile_b = SimpleNamespace(
        average=float(record.player_b_average),
        checkout=float(record.player_b_checkout),
    )

    simulation = simulate_match(
        profile_a,
        profile_b,
        leg_win_prob_a=leg_probability,
        best_of=int(record.best_of),
    )

    return {
        "leg_win_probability": leg_probability,
        "handicap_probability": handicap_cover_probability(
            simulation,
            player="a",
            line=handicap_line,
        ),
        "total_legs_over_probability": total_legs_over_probability(
            simulation,
            line=total_legs_line,
        ),
    }




def evaluate_candidate_fixed_holdout(
    train,
    test,
    *,
    average_weight,
    checkout_weight,
    logistic_scale,
    market,
    handicap_line=-1.5,
    total_legs_line=5.5,
):
    from dataclasses import replace

    from app.services.leg_market_walk_forward_service import (
        evaluate_fixed_holdout,
    )

    if market not in {"handicap", "total_legs"}:
        raise ValueError(
            "market must be 'handicap' or 'total_legs'."
        )

    def candidate_records(records):
        recalculated = []

        for record in records:
            probabilities = candidate_market_probabilities(
                record,
                average_weight=average_weight,
                checkout_weight=checkout_weight,
                logistic_scale=logistic_scale,
                handicap_line=handicap_line,
                total_legs_line=total_legs_line,
            )

            recalculated.append(
                replace(
                    record,
                    player_a_leg_win_probability=(
                        probabilities["leg_win_probability"]
                    ),
                    player_a_handicap_probability=(
                        probabilities["handicap_probability"]
                    ),
                    total_legs_over_probability=(
                        probabilities[
                            "total_legs_over_probability"
                        ]
                    ),
                )
            )

        return tuple(recalculated)

    candidate_train = candidate_records(train)
    candidate_test = candidate_records(test)

    if market == "handicap":
        probability_attr = "player_a_handicap_probability"
        result_attr = "player_a_handicap_result"
    else:
        probability_attr = "total_legs_over_probability"
        result_attr = "total_legs_over_result"

    return evaluate_fixed_holdout(
        candidate_train,
        candidate_test,
        probability_attr=probability_attr,
        result_attr=result_attr,
    )



def evaluate_candidate_date_disjoint_walk_forward(
    records,
    *,
    average_weight,
    checkout_weight,
    logistic_scale,
    market,
    initial_train_size,
    test_size,
    handicap_line=-1.5,
    total_legs_line=5.5,
):
    from dataclasses import replace

    from app.services.leg_market_walk_forward_service import (
        evaluate_date_disjoint_walk_forward,
    )

    if market not in {"handicap", "total_legs"}:
        raise ValueError(
            "market must be 'handicap' or 'total_legs'."
        )

    candidate_records = []

    for record in records:
        probabilities = candidate_market_probabilities(
            record,
            average_weight=average_weight,
            checkout_weight=checkout_weight,
            logistic_scale=logistic_scale,
            handicap_line=handicap_line,
            total_legs_line=total_legs_line,
        )

        candidate_records.append(
            replace(
                record,
                player_a_leg_win_probability=(
                    probabilities["leg_win_probability"]
                ),
                player_a_handicap_probability=(
                    probabilities["handicap_probability"]
                ),
                total_legs_over_probability=(
                    probabilities[
                        "total_legs_over_probability"
                    ]
                ),
            )
        )

    if market == "handicap":
        probability_attr = "player_a_handicap_probability"
        result_attr = "player_a_handicap_result"
    else:
        probability_attr = "total_legs_over_probability"
        result_attr = "total_legs_over_result"

    return evaluate_date_disjoint_walk_forward(
        candidate_records,
        probability_attr=probability_attr,
        result_attr=result_attr,
        initial_train_size=initial_train_size,
        test_size=test_size,
    )



def evaluate_candidate_walk_forward(
    records,
    *,
    average_weight,
    checkout_weight,
    logistic_scale,
    market,
    initial_train_size,
    test_size,
    handicap_line=-1.5,
    total_legs_line=5.5,
):
    from dataclasses import replace

    from app.services.leg_market_walk_forward_service import (
        evaluate_walk_forward,
    )

    if market not in {"handicap", "total_legs"}:
        raise ValueError(
            "market must be 'handicap' or 'total_legs'."
        )

    candidate_records = []

    for record in records:
        probabilities = candidate_market_probabilities(
            record,
            average_weight=average_weight,
            checkout_weight=checkout_weight,
            logistic_scale=logistic_scale,
            handicap_line=handicap_line,
            total_legs_line=total_legs_line,
        )

        candidate_records.append(
            replace(
                record,
                player_a_leg_win_probability=(
                    probabilities["leg_win_probability"]
                ),
                player_a_handicap_probability=(
                    probabilities["handicap_probability"]
                ),
                total_legs_over_probability=(
                    probabilities[
                        "total_legs_over_probability"
                    ]
                ),
            )
        )

    if market == "handicap":
        probability_attr = "player_a_handicap_probability"
        result_attr = "player_a_handicap_result"
    else:
        probability_attr = "total_legs_over_probability"
        result_attr = "total_legs_over_result"

    return evaluate_walk_forward(
        candidate_records,
        probability_attr=probability_attr,
        result_attr=result_attr,
        initial_train_size=initial_train_size,
        test_size=test_size,
    )
