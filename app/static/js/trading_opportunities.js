document.addEventListener("DOMContentLoaded", () => {
    const oddsInputs =
        document.querySelectorAll(".bookmaker-odds");

    oddsInputs.forEach((input) => {
        const row = input.closest("tr");
        const button =
            row.querySelector(".add-paper-trade");

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
                selection: button.dataset.selection,
                odds: Number(button.dataset.bookmaker),
                stake: 1.0,
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
            const fairOdds =
                parseFloat(input.dataset.fair);

            const minimumOdds =
                parseFloat(
                    row.querySelector(
                        ".minimum-odds"
                    ).dataset.minimum
                );

            const bookmakerOdds =
                parseFloat(input.value);

            const edgeCell =
                row.querySelector(".edge-value");

            const badge =
                row.querySelector(".value-status");

            button.textContent = "➕";

            button.classList.remove(
                "saved",
                "already-saved"
            );

            if (
                Number.isNaN(fairOdds) ||
                Number.isNaN(minimumOdds) ||
                Number.isNaN(bookmakerOdds) ||
                bookmakerOdds < 1.01
            ) {
                edgeCell.textContent = "—";

                badge.textContent = "Waiting";
                badge.className =
                    "value-status badge badge-secondary";

                button.disabled = true;

                delete button.dataset.bookmaker;
                delete button.dataset.edge;

                return;
            }

            const edge =
                ((bookmakerOdds / fairOdds) - 1) * 100;

            edgeCell.textContent =
                `${edge.toFixed(1)}%`;

            button.dataset.bookmaker =
                bookmakerOdds.toFixed(2);

            button.dataset.edge =
                edge.toFixed(2);

            if (bookmakerOdds >= minimumOdds) {
                badge.textContent = "VALUE";
                badge.className =
                    "value-status badge badge-success";

                button.disabled = false;

            } else if (bookmakerOdds >= fairOdds) {
                badge.textContent = "FAIR";
                badge.className =
                    "value-status badge badge-warning";

                button.disabled = false;

            } else {
                badge.textContent = "PASS";
                badge.className =
                    "value-status badge badge-danger";

                button.disabled = true;
            }
        });
    });
});