from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel
from src.agent_engine_client import get_agent_client

app = FastAPI()

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

class AskRequest(BaseModel):
    question: str

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.post("/api/ask")
async def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        client = get_agent_client()
        answer = await client.async_stream_query(question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Agent Engine invocation failed.")

@app.post("/api/analyze")
async def analyze():
    prompt = "Use the deterministic_clearance tool on data/fixtures/project_aurora_valid.json. Do not make the clearance decision yourself. Report the authoritative clearance result."
    try:
        client = get_agent_client()
        result = await client.analyze_clearance(prompt)

        clearance_result = result["clearance_result"]

        # Validate authoritative payload
        if not (
            isinstance(clearance_result, dict) and
            isinstance(clearance_result.get("status"), str) and clearance_result.get("status") and
            isinstance(clearance_result.get("summary"), dict) and
            all(isinstance(clearance_result["summary"].get(k), int) for k in ["total_usages", "cleared", "not_cleared"]) and
            isinstance(clearance_result.get("decisions"), list)
        ):
            raise ValueError("Malformed authoritative clearance data")

        return {
            "answer": result["answer"],
            "overall_status": clearance_result.get("status"),
            "summary": clearance_result.get("summary"),
            "decisions": clearance_result.get("decisions"),
            "authoritative_source": "deterministic_clearance"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Rights analysis could not be completed.")
