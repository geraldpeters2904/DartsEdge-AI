"""Application release metadata for DartsEdge AI."""

APP_NAME = "DartsEdge AI"
VERSION = "1.1.1"
BUILD = "006"
RELEASE_NAME = "Mission Control"


def version_payload() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "version": VERSION,
        "build": BUILD,
        "release": RELEASE_NAME,
        "display": f"{APP_NAME} v{VERSION} (build {BUILD})",
    }
