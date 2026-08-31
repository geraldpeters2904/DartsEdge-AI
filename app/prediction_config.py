"""Active production prediction-model configuration.

This module provides the single authoritative model selector for
live DartsEdge AI prediction workflows.

Changing ACTIVE_PREDICTION_MODEL_NAME is a production model promotion
or rollback decision and should only be done after validation.
"""

ACTIVE_PREDICTION_MODEL_NAME = "transparent-v3.5"
