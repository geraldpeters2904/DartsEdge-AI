from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True)
class CaptureRequest:
    match_id: int
    source_url: str
    destination_folder: Path
    destination_filename: str
    player_a_name: str
    player_b_name: str

    @property
    def destination_path(self) -> Path:
        return (
            self.destination_folder
            / self.destination_filename
        )


@dataclass(frozen=True)
class CaptureResult:
    provider: str
    status: str
    match_id: int
    destination_path: Optional[Path]
    message: str

    html: Optional[str] = None
    source_url: Optional[str] = None
    page_title: Optional[str] = None
    captured_at: Optional[str] = None
    error: Optional[str] = None
    bytes_written: Optional[int] = None

    @property
    def successful(self) -> bool:
        return self.status == "captured"

    @property
    def waiting(self) -> bool:
        return self.status == "waiting"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @property
    def has_html(self) -> bool:
        return bool((self.html or "").strip())


class CaptureProvider(Protocol):
    name: str

    def capture(
        self,
        request: CaptureRequest,
    ) -> CaptureResult:
        """Attempt to obtain one match page."""
        ...
