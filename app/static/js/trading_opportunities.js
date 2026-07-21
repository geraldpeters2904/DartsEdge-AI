document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".bookmaker-odds").forEach((input) => {
        input.addEventListener("input", () => {
            const row = input.closest("tr");
            const fairOdds = parseFloat(input.dataset.fair);
            const minimumOdds = parseFloat(
                row.querySelector(".minimum-odds").dataset.minimum
            );
            const bookmakerOdds = parseFloat(input.value);

            const edgeCell = row.querySelector(".edge-value");
            const badge = row.querySelector(".value-status");
            const button = row.querySelector(".add-paper-trade");

            if (
                Number.isNaN(fairOdds) ||
                Number.isNaN(bookmakerOdds) ||
                bookmakerOdds < 1.01
            ) {
                edgeCell.textContent = "—";
                badge.textContent = "Waiting";
                badge.className =
                    "value-status badge badge-secondary";
                button.disabled = true;
                return;
            }

            const edge =
                ((bookmakerOdds / fairOdds) - 1) * 100;

            edgeCell.textContent = `${edge.toFixed(1)}%`;

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