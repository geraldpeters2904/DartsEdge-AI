from fastapi.templating import Jinja2Templates

from app.services.display_service import display_name

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["display_name"] = display_name