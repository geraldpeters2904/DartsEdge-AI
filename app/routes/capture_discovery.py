from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse
from urllib.parse import quote

from app.services.capture_discovery_service import CaptureDiscoveryService
from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT


router = APIRouter()
discovery_service = CaptureDiscoveryService()


@router.post("/admin/collector/captures/discover")
def discover_capture_sessions(root: str = Form("")):
    selected_root = root or str(DEFAULT_CAPTURE_ROOT)

    try:
        report = discovery_service.discover(selected_root, repair=True)
        message = (
            f"Discovery complete: {report.discovered_session_files} sessions, "
            f"{report.repaired_sessions} repaired, {len(report.issues)} issues."
        )
        return RedirectResponse(
            "/admin/collector/captures?root="
            + quote(str(report.root))
            + "&message="
            + quote(message),
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(
            "/admin/collector/captures?message=" + quote(f"Discovery failed: {exc}"),
            status_code=303,
        )
