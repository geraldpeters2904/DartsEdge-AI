from fastapi import APIRouter, Request

from app.templates_config import templates


router = APIRouter()


@router.get("/admin/collector")
def collector_page(request: Request):
    return templates.TemplateResponse(
        request,
        "collector.html",
        {
            "supported_files": (
                "fixtures.csv",
                "results.csv",
                "statistics.csv",
                "odds.csv",
            ),
            "message": request.query_params.get("message"),
        },
    )
