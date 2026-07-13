def build_confidence_bands(predictions):
    bands = {
        "50-59": {"total": 0, "correct": 0},
        "60-69": {"total": 0, "correct": 0},
        "70-79": {"total": 0, "correct": 0},
        "80-89": {"total": 0, "correct": 0},
        "90-100": {"total": 0, "correct": 0},
    }

    for prediction in predictions:
        if prediction.winner_correct is None:
            continue

        confidence = prediction.confidence or 0

        if confidence < 60:
            band = "50-59"
        elif confidence < 70:
            band = "60-69"
        elif confidence < 80:
            band = "70-79"
        elif confidence < 90:
            band = "80-89"
        else:
            band = "90-100"

        bands[band]["total"] += 1

        if prediction.winner_correct == 1:
            bands[band]["correct"] += 1

    rows = []

    for label, values in bands.items():
        total = values["total"]
        correct = values["correct"]

        accuracy = round((correct / total) * 100, 1) if total else 0

        rows.append({
            "band": label,
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
        })

    return rows