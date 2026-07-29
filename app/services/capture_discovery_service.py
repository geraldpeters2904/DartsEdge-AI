from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.modus_capture_session_service import ModusCaptureSessionService, SESSION_FILENAME


@dataclass(frozen=True)
class CaptureDiscoveryIssue:
    folder: Path
    code: str
    message: str


@dataclass(frozen=True)
class CaptureDiscoveryReport:
    root: Path
    discovered_session_files: int
    repaired_sessions: int
    untracked_results_folders: int
    issues: List[CaptureDiscoveryIssue]


class CaptureDiscoveryService:
    """Discover and repair offline capture sessions below a capture root."""

    def __init__(self):
        self.session_service = ModusCaptureSessionService()

    def discover(self, root: str | Path = DEFAULT_CAPTURE_ROOT, *, repair: bool = True) -> CaptureDiscoveryReport:
        capture_root = Path(root).expanduser().resolve()
        capture_root.mkdir(parents=True, exist_ok=True)

        if not capture_root.is_dir():
            raise ValueError(f"Capture discovery root is not a folder: {capture_root}")

        repaired = 0
        untracked = 0
        issues: List[CaptureDiscoveryIssue] = []

        for results_file in sorted(capture_root.rglob("results.html")):
            folder = results_file.parent
            session_file = folder / SESSION_FILENAME
            if session_file.exists():
                continue

            untracked += 1
            if not repair:
                continue

            try:
                self.session_service.create_session(
                    results_filename="results.html",
                    results_html=results_file.read_text(encoding="utf-8"),
                    destination_folder=folder,
                )
                repaired += 1
            except Exception as exc:
                issues.append(CaptureDiscoveryIssue(
                    folder=folder,
                    code="session_repair_failed",
                    message=str(exc),
                ))

        return CaptureDiscoveryReport(
            root=capture_root,
            discovered_session_files=len(list(capture_root.rglob(SESSION_FILENAME))),
            repaired_sessions=repaired,
            untracked_results_folders=untracked,
            issues=issues,
        )
