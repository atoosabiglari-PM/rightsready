from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")
