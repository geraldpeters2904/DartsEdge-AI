from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Dict, List, Optional


SESSION_FILENAMES = (
    ".modus_capture_session.json",
    "modus_capture_session.json",
)
HTML_SUFFIXES = (".html", ".htm")


@dataclass
class CaptureAssistantEvent:
    timestamp: str
    level: str
    message: str
    filename: Optional[str] = None


@dataclass
class CaptureAssistantStatus:
    running: bool
    destination_folder: str
    watch_folder: str
    expected_match_id: Optional[int]
    expected_filename: Optional[str]
    accepted_count: int
    rejected_count: int
    last_message: str
    events: List[Dict[str, object]]


class ModusCaptureAssistantService:
    """
    Poll a local watch folder for newly saved MODUS HTML pages.

    The service accepts only the currently expected match page, renames it to
    match_<id>.html, moves it into the capture folder, and advances by reading
    the capture session JSON again. It never makes live HTTP requests.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._destination = Path()
        self._watch = Path()
        self._seen: Dict[str, float] = {}
        self._accepted = 0
        self._rejected = 0
        self._last_message = "Assistant has not started."
        self._events: List[CaptureAssistantEvent] = []

    def start(
        self,
        destination_folder: str,
        watch_folder: str,
    ) -> CaptureAssistantStatus:
        destination = Path(destination_folder).expanduser().resolve()
        watch = Path(watch_folder).expanduser().resolve()

        if not destination.is_dir():
            raise ValueError(
                "Destination capture folder does not exist: "
                + str(destination)
            )
        if not watch.is_dir():
            raise ValueError(
                "Watch folder does not exist: " + str(watch)
            )

        self._find_session_file(destination)

        with self._lock:
            if self._running:
                self.stop()

            self._destination = destination
            self._watch = watch
            self._seen = {
                str(path): path.stat().st_mtime
                for path in watch.iterdir()
                if path.is_file()
            }
            self._accepted = 0
            self._rejected = 0
            self._events = []
            self._stop_event.clear()
            self._running = True
            self._record(
                "info",
                "Assisted capture started. Save the expected MODUS match "
                "page into the watch folder.",
            )

            self._thread = threading.Thread(
                target=self._run,
                name="dartsedge-modus-capture-assistant",
                daemon=True,
            )
            self._thread.start()

        return self.status()

    def stop(self) -> CaptureAssistantStatus:
        with self._lock:
            self._stop_event.set()
            self._running = False
            self._record("info", "Assisted capture stopped.")
        return self.status()

    def status(self) -> CaptureAssistantStatus:
        with self._lock:
            expected = None
            try:
                if self._destination:
                    expected = self._expected_item(self._destination)
            except Exception as exc:
                self._last_message = str(exc)

            return CaptureAssistantStatus(
                running=self._running,
                destination_folder=(
                    str(self._destination) if self._destination else ""
                ),
                watch_folder=str(self._watch) if self._watch else "",
                expected_match_id=(
                    expected["match_id"] if expected else None
                ),
                expected_filename=(
                    expected["filename"] if expected else None
                ),
                accepted_count=self._accepted,
                rejected_count=self._rejected,
                last_message=self._last_message,
                events=[
                    asdict(event)
                    for event in list(reversed(self._events[-30:]))
                ],
            )

    def process_once(self) -> None:
        with self._lock:
            if not self._running:
                return
            destination = self._destination
            watch = self._watch

        expected = self._expected_item(destination)
        if expected is None:
            with self._lock:
                self._last_message = "Capture session is complete."
                self._record("success", self._last_message)
                self._running = False
                self._stop_event.set()
            return

        candidates = []
        for path in watch.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() not in HTML_SUFFIXES:
                continue
            if path.name.startswith("."):
                continue

            mtime = path.stat().st_mtime
            old_mtime = self._seen.get(str(path))
            if old_mtime is None or mtime > old_mtime:
                candidates.append(path)
                self._seen[str(path)] = mtime

        for path in sorted(candidates, key=lambda item: item.stat().st_mtime):
            if not self._file_is_stable(path):
                continue
            self._process_file(path, expected)
            break

    def _run(self) -> None:
        while not self._stop_event.wait(1.0):
            try:
                self.process_once()
            except Exception as exc:
                with self._lock:
                    self._last_message = "Assistant error: " + str(exc)
                    self._record("error", self._last_message)

    def _process_file(
        self,
        source: Path,
        expected: Dict[str, object],
    ) -> None:
        html = source.read_text(encoding="utf-8", errors="ignore")
        match_id = int(expected["match_id"])
        filename = str(expected["filename"])

        if not self._looks_like_expected_match(
            html,
            match_id,
            str(expected.get("player_a") or ""),
            str(expected.get("player_b") or ""),
        ):
            with self._lock:
                self._rejected += 1
                self._last_message = (
                    "Ignored " + source.name
                    + ": it does not match expected MODUS match "
                    + str(match_id) + "."
                )
                self._record(
                    "warning",
                    self._last_message,
                    source.name,
                )
            return

        target = self._destination / filename
        if target.exists():
            existing = target.read_bytes()
            incoming = source.read_bytes()
            if existing == incoming:
                source.unlink()
                message = (
                    "Removed duplicate saved file; "
                    + filename + " is already captured."
                )
                with self._lock:
                    self._last_message = message
                    self._record("info", message, source.name)
                return

            with self._lock:
                self._rejected += 1
                self._last_message = (
                    "Conflict: " + filename
                    + " already exists with different content."
                )
                self._record(
                    "error",
                    self._last_message,
                    source.name,
                )
            return

        shutil.move(str(source), str(target))

        with self._lock:
            self._accepted += 1
            self._last_message = (
                "Accepted " + target.name
                + ". Capture progress advanced."
            )
            self._record(
                "success",
                self._last_message,
                target.name,
            )

    @staticmethod
    def _looks_like_expected_match(
        html: str,
        match_id: int,
        player_a: str,
        player_b: str,
    ) -> bool:
        lowered = html.casefold()
        id_patterns = (
            str(match_id),
            "matchid=" + str(match_id),
            "match/" + str(match_id),
            "match_" + str(match_id),
        )
        id_matches = any(
            pattern.casefold() in lowered
            for pattern in id_patterns
        )

        names = [
            name.strip().casefold()
            for name in (player_a, player_b)
            if name and name.strip()
        ]
        names_match = (
            len(names) == 2
            and all(name in lowered for name in names)
        )

        # Prefer an explicit match ID, but Safari-saved MODUS pages may omit
        # it from the page source. In that case, require both expected player
        # names as the safe fallback.
        return id_matches or names_match

    @staticmethod
    def _file_is_stable(path: Path) -> bool:
        try:
            first = path.stat().st_size
            time.sleep(0.25)
            second = path.stat().st_size
            return first > 0 and first == second
        except FileNotFoundError:
            return False

    @staticmethod
    def _find_session_file(destination: Path) -> Path:
        for filename in SESSION_FILENAMES:
            path = destination / filename
            if path.is_file():
                return path
        raise ValueError(
            "No MODUS capture session JSON was found in "
            + str(destination)
        )

    def _expected_item(
        self,
        destination: Path,
    ) -> Optional[Dict[str, object]]:
        session_path = self._find_session_file(destination)
        payload = json.loads(session_path.read_text(encoding="utf-8"))

        items = payload.get("items") or payload.get("matches") or []
        for item in items:
            match_id = (
                item.get("match_id")
                or item.get("id")
                or item.get("external_id")
            )
            if match_id is None:
                continue

            match_id = int(
                re.sub(r"\D", "", str(match_id))
            )
            filename = (
                item.get("filename")
                or "match_" + str(match_id) + ".html"
            )

            if not (destination / filename).is_file():
                players = item.get("players") or []
                player_a = (
                    item.get("player_a")
                    or item.get("player_a_name")
                    or (players[0] if len(players) > 0 else "")
                )
                player_b = (
                    item.get("player_b")
                    or item.get("player_b_name")
                    or (players[1] if len(players) > 1 else "")
                )
                return {
                    "match_id": match_id,
                    "filename": filename,
                    "player_a": player_a,
                    "player_b": player_b,
                }

        return None

    def _record(
        self,
        level: str,
        message: str,
        filename: Optional[str] = None,
    ) -> None:
        self._last_message = message
        self._events.append(
            CaptureAssistantEvent(
                timestamp=datetime.utcnow().isoformat(),
                level=level,
                message=message,
                filename=filename,
            )
        )
