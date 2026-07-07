K_FACTOR = 32


def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_elo(player_a, player_b, winner):

    expected_a = expected_score(player_a.elo, player_b.elo)
    expected_b = expected_score(player_b.elo, player_a.elo)

    actual_a = 1 if winner == player_a.name else 0
    actual_b = 1 if winner == player_b.name else 0

    player_a.elo = round(
        player_a.elo + K_FACTOR * (actual_a - expected_a)
    )

    player_b.elo = round(
        player_b.elo + K_FACTOR * (actual_b - expected_b)
    )