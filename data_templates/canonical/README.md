# DartsEdge Canonical CSV Templates

These CSV templates define the standard import format used by the DartsEdge
Collector.

## Templates

- fixtures.csv
- results.csv
- statistics.csv
- odds.csv

A collection session may contain any combination of these files.

## Date and time

Use ISO-8601 format.

Examples:

2026-07-28T10:00:00
2026-07-28T10:00:00+01:00
2026-07-28T09:00:00Z

## Missing values

Leave the field blank if the value is unknown.

Do not enter zero unless the source explicitly reports zero.

Example:

scores_180

blank = unknown

0 = confirmed zero

## Source information

Every imported row should preserve:

- source_provider
- source_external_id
- source_retrieved_at
- source_competition_code
- source_confidence

## Current supported market

match_winner

Additional markets will be added in future releases.
