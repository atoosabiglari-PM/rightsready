# RightsReady

AI rights-clearance control center for film and media production.

**AI ORCHESTRATES. RULES GOVERN. DATA PROVES.**

Film/media teams need rapid rights clearance while AI systems must not invent legal clearance decisions. RightsReady uses Gemini to orchestrate the workflow, deterministic tools to make authoritative legal decisions based on provided rights data, and ClickHouse to provide live rights intelligence through MCP.

## Live Demo
https://rightsready-web-550358050067.us-central1.run.app

## Architecture
Gemini orchestrates and explains the process, while deterministic tools make the authoritative clearance decisions, ensuring governance boundaries are respected.

### Workflow
1. **Clearance:** Gemini -> `deterministic_clearance` tool -> Authoritative governed result.
2. **Warehouse Intelligence:** Gemini -> `agent_query_warehouse` tool -> MCP -> ClickHouse.

## Technology Stack
- **AI/Orchestration:** Google Gemini, Vertex AI Agent Engine, Google ADK.
- **Backend:** FastAPI, Uvicorn, Jinja2.
- **Database/Intelligence:** ClickHouse, MCP.
- **Deployment:** Google Cloud Run.

## Documentation
- [Architecture](docs/architecture.md)
- [Setup](docs/setup.md)
- [Security & Governance](docs/security-governance.md)

## License
Apache License 2.0
