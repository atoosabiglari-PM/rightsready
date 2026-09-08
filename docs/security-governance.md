# Security & Governance

RightsReady adheres to a strict "fail-closed" governance model.

- **Authoritative Boundary:** Legal clearance decisions are made by deterministic code, NOT by Gemini. Gemini orchestrates and explains, but the `deterministic_clearance` tool applies the authoritative business logic.
- **Data Integrity:** ClickHouse is accessed via read-only MCP queries, ensuring raw database payloads are never exposed to the frontend.
- **Safe Rendering:** The frontend uses standard template rendering; no raw `innerHTML` injection or browser-side credential access is permitted.
- **Runtime Identity:** Authentication to Vertex AI and Agent Engine is handled via Cloud Run service identity, not application-level secrets or keys.
- **Operational Safety:** The `/health` endpoint is lightweight and does NOT invoke expensive or live backend services.
