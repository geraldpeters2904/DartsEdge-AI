def dartsedge_rating(profile):
    """
    Calculate a DartsEdge rating out of 100.
    """

    elo = profile.get("elo", 1200)
    average = profile.get("average", 0)
    checkout = profile.get("checkout", 0)
    one80 = profile["form"].get("expected", 0)
    confidence = profile.get("confidence", 50)

    # Scale each component

    elo_score = min(max((elo - 1200) / 6, 0), 100)
    average_score = min(max(average, 0), 100)
    checkout_score = min(max(checkout * 2, 0), 100)
    one80_score = min(max(one80 * 25, 0), 100)

    rating = (
        elo_score * 0.35 +
        average_score * 0.25 +
        checkout_score * 0.15 +
        one80_score * 0.15 +
        confidence * 0.10
    )

    return round(rating, 1)