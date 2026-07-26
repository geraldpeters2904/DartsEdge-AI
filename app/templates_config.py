from __future__ import annotations

from typing import Any

from fastapi.templating import Jinja2Templates

from app.services.display_service import display_name
from app.version import BUILD, VERSION


class DartsEdgeTemplates(Jinja2Templates):
    """Template engine accepting legacy calls without Starlette deprecation warnings.

    Existing routes historically call ``TemplateResponse(name, context)``. This
    adapter normalises those calls to Starlette's current request-first API,
    allowing routes to be modernised gradually without noisy test output.
    """

    def TemplateResponse(self, *args: Any, **kwargs: Any):  # noqa: N802 - Starlette API name
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.pop("context", {})
            request = context.get("request")
            if request is None:
                raise ValueError('context must include a "request" key')
            status_code = args[2] if len(args) > 2 else kwargs.pop("status_code", 200)
            headers = args[3] if len(args) > 3 else kwargs.pop("headers", None)
            media_type = args[4] if len(args) > 4 else kwargs.pop("media_type", None)
            background = args[5] if len(args) > 5 else kwargs.pop("background", None)
            return super().TemplateResponse(
                request,
                name,
                context,
                status_code,
                headers,
                media_type,
                background,
            )
        return super().TemplateResponse(*args, **kwargs)


templates = DartsEdgeTemplates(directory="app/templates")
templates.env.filters["display_name"] = display_name
templates.env.globals.update(app_version=VERSION, app_build=BUILD)
