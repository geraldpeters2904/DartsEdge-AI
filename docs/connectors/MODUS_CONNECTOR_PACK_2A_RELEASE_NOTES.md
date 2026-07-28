# MODUS Connector Pack 2A — Real Results Parser

## Added

- DOM-style parsing through Python's standard `HTMLParser`.
- Discovery of the selected Series, Week and active Group.
- Extraction of every real MODUS fixture card.
- Match number, `match_id`, players and scores.
- Group table extraction.
- Rich `ModusResultsPageRecord` and `ModusGroupTableRecord` schemas.
- Regression fixture based on a genuine saved MODUS Series 14, Week 13, Group A page.
- Focused parser tests.

## Safety

- No live website requests.
- No automated retrieval.
- Existing Pack 1 synthetic fixtures remain supported.
