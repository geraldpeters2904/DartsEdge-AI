"""Official DartsEdge canonical CSV column definitions."""

CSV_REQUIRED_HEADERS = {
    "fixtures": (
        "external_id",
        "competition_code",
        "competition_name",
        "scheduled_at",
        "player_a_external_id",
        "player_a_name",
        "player_b_external_id",
        "player_b_name",
    ),
    "results": (
        "match_external_id",
        "player_a_external_id",
        "player_b_external_id",
        "winner_external_id",
        "player_a_legs",
        "player_b_legs",
    ),
    "statistics": (
        "match_external_id",
        "player_external_id",
    ),
    "odds": (
        "match_external_id",
        "market",
        "selection_name",
        "bookmaker",
        "decimal_odds",
        "captured_at",
    ),
}

CSV_OPTIONAL_HEADERS = {
    "fixtures": (
        "season",
        "series",
        "week",
        "group",
        "stage",
        "actual_start_at",
        "status",
        "match_format",
        "board",
        "session",
        "throwing_first_player_external_id",
    ),
    "results": (
        "completed_at",
        "first_leg_winner_external_id",
        "first_180_player_external_id",
    ),
    "statistics": (
        "three_dart_average",
        "first_nine_average",
        "scores_100_plus",
        "scores_140_plus",
        "scores_180",
        "checkout_attempts",
        "checkouts_completed",
        "checkout_percentage",
        "highest_checkout",
        "legs_won",
        "legs_lost",
        "legs_held",
        "legs_broken",
        "match_duration_seconds",
    ),
    "odds": (
        "selection_external_id",
    ),
}

CSV_SOURCE_HEADERS = (
    "source_provider",
    "source_external_id",
    "source_retrieved_at",
    "source_competition_code",
    "source_confidence",
)


def allowed_headers(entity_type: str):
    if entity_type not in CSV_REQUIRED_HEADERS:
        raise ValueError(f"Unsupported CSV entity type: {entity_type}")

    return (
        CSV_REQUIRED_HEADERS[entity_type]
        + CSV_OPTIONAL_HEADERS[entity_type]
        + CSV_SOURCE_HEADERS
    )
