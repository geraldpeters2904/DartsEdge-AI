document.addEventListener("DOMContentLoaded", () => {
    const oddsInputs =
        document.querySelectorAll(".bookmaker-odds");

    oddsInputs.forEach((input) => {
        const row = input.closest("tr");
        const button =
            row.querySelector(".add-paper-trade");

        let evaluationTimer = null;

        button.addEventListener("click", async () => {
            if (button.disabled) {
                return;
            }

            const originalText = button.textContent;

            button.disabled = true;
            button.textContent = "Saving...";

            const tradeData = {
                prediction_id: Number(
                    button.dataset.predictionId
                ),
                market: button.dataset.market,
                decision_market:
                    button.dataset.decisionMarket,
                selection: button.dataset.selection,
                odds: Number(button.dataset.bookmaker),
                model_probability: Number(
                    button.dataset.probability
                ),
                confidence_percent: Number(
                    button.dataset.confidence
                ),
                sample_size: Number(
                    button.dataset.sampleSize
                ),
                competition:
                    button.dataset.competition || "",
                bookmaker: "Trading Opportunities",
            };

            try {
                const response = await fetch(
                    "/api/paper-trades",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json",
                        },
                        body: JSON.stringify(tradeData),
                    }
                );

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(
                        result.detail ||
                        "Paper trade could not be saved"
                    );
                }

                if (result.already_exists) {
                    button.textContent =
                        "✓ Already Saved";

                    button.classList.remove("saved");
                    button.classList.add(
                        "already-saved"
                    );

                    button.disabled = true;

                    alert(
                        result.message ||
                        "This paper trade already exists."
                    );

                    return;
                }

                button.textContent = "✓ Saved";

                button.classList.remove(
                    "already-saved"
                );

                button.classList.add("saved");
                button.disabled = true;

                alert(
                    result.message ||
                    "Paper trade saved successfully."
                );

            } catch (error) {
                console.error(
                    "Paper trade save error:",
                    error
                );

                button.textContent = originalText;
                button.disabled = false;

                alert(
                    `Unable to save paper trade: ${error.message}`
                );
            }
        });

        input.addEventListener("input", () => {
            const bookmakerOdds =
                parseFloat(input.value);

            const edgeCell =
                row.querySelector(".edge-value");
            const badge =
                row.querySelector(".value-status");
            const kellyCell =
                row.querySelector(".kelly-percent");
            const stakeCell =
                row.querySelector(".effective-stake");
            const evCell =
                row.querySelector(".expected-value");
            const riskCell =
                row.querySelector(".risk-level");

            clearTimeout(evaluationTimer);

            button.textContent = "➕";
            button.disabled = true;
            button.classList.remove(
                "saved",
                "already-saved"
            );

            delete button.dataset.bookmaker;
            delete button.dataset.edge;
            delete button.dataset.rawKellyStake;
            delete button.dataset.effectiveStake;
            delete button.dataset.strategyName;

            if (
                Number.isNaN(bookmakerOdds) ||
                bookmakerOdds < 1.01
            ) {
                edgeCell.textContent = "—";
                stakeCell.textContent = "—";

                badge.textContent = "Waiting";
                badge.className =
                    "value-status badge badge-secondary";

                return;
            }

            badge.textContent = "Checking";
            badge.className =
                "value-status badge badge-secondary";

            evaluationTimer = setTimeout(async () => {
                const evaluationData = {
                    prediction_id: Number(
                        button.dataset.predictionId
                    ),
                    market: button.dataset.decisionMarket,
                    selection: button.dataset.selection,
                    odds: bookmakerOdds,
                    model_probability: Number(
                        button.dataset.probability
                    ),
                    confidence_percent: Number(
                        button.dataset.confidence
                    ),
                    sample_size: Number(
                        button.dataset.sampleSize
                    ),
                    competition:
                        button.dataset.competition || "",
                    bookmaker: "Trading Opportunities",
                };

                try {
                    const response = await fetch(
                        "/api/trading-opportunities/evaluate",
                        {
                            method: "POST",
                            headers: {
                                "Content-Type":
                                    "application/json",
                            },
                            body: JSON.stringify(
                                evaluationData
                            ),
                        }
                    );

                    const result = await response.json();

                    if (!response.ok) {
                        throw new Error(
                            result.detail ||
                            "Opportunity could not be evaluated"
                        );
                    }

                    const decision =
                        result.decision_engine;

                    edgeCell.textContent =
                        `${result.edge_percent.toFixed(1)}%`;
                    kellyCell.textContent =
                        `${result.kelly_percent.toFixed(2)}%`;
                    stakeCell.textContent =
                        `£${decision.effective_stake.toFixed(2)}`;
                    evCell.textContent =
                        `${result.expected_value_percent.toFixed(2)}%`;
                    riskCell.textContent =
                        result.risk_level;

                    button.dataset.bookmaker =
                        bookmakerOdds.toFixed(2);
                    button.dataset.edge =
                        result.edge_percent.toFixed(2);
                    button.dataset.rawKellyStake =
                        result.raw_kelly_stake.toFixed(2);
                    button.dataset.effectiveStake =
                        decision.effective_stake.toFixed(2);
                    button.dataset.strategyName =
                        decision.strategy_name || "";

                    if (
                        decision.effective_decision !== "Reject" &&
                        decision.effective_stake > 0
                    ) {
                        badge.textContent =
                            decision.effective_decision;
                        badge.className =
                            "value-status badge badge-success";
                        button.disabled = false;
                    } else {
                        badge.textContent =
                            decision.effective_decision;
                        badge.className =
                            "value-status badge badge-danger";
                        button.disabled = true;
                    }

                } catch (error) {
                    console.error(
                        "Opportunity evaluation error:",
                        error
                    );

                    edgeCell.textContent = "—";
                    stakeCell.textContent = "—";

                    badge.textContent = "Error";
                    badge.className =
                        "value-status badge badge-danger";

                    button.disabled = true;
                }
            }, 300);
        });
    });
});