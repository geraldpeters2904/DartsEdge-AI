"""Application release metadata for DartsEdge AI."""

APP_NAME = "DartsEdge AI"
VERSION = "1.4.0"
BUILD = "001"
RELEASE_NAME = "Strategy Engine"
MODEL_VERSION = "Intelligence-0.1-shadow"


def version_payload() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "version": VERSION,
        "build": BUILD,
        "release": RELEASE_NAME,
        "model_version": MODEL_VERSION,
        "display": f"{APP_NAME} v{VERSION} (build {BUILD})",
    }
