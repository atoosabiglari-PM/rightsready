# Architecture

RightsReady implements a strict governance boundary between AI orchestration and authoritative clearance decisions.

## Architecture Diagram
```mermaid
graph TD
    JudgeBrowser[Judge Browser] -->|HTTPS| CloudRun[Cloud Run / FastAPI]
    CloudRun -->|REST| AgentEngine[Vertex AI Agent Engine]
    AgentEngine -->|Orchestrate| ADKGemini[Google ADK Agent + Gemini]
    ADKGemini -->|Invoke| DetTool[Deterministic Tools]
    ADKGemini -->|Invoke| MCP[MCP Tool]
    DetTool -->|Clearance Engine| RightsEngine[RightsReady Engine]
    MCP -->|Query| ClickHouse[ClickHouse]
    RightsEngine -->|Authoritative Decision| ADKGemini
    ClickHouse -->|Normalized Evidence| ADKGemini
```

## Clearance Workflow
AI is NOT the legal decision authority.
1. **Clearance Path:** Gemini orchestrates the process, calls the `deterministic_clearance` tool, which applies business rules to assets against license data, producing an **authoritative governed result**.
2. **Intelligence Path:** Gemini calls the `agent_query_warehouse` tool via MCP to retrieve live rights data from ClickHouse for contextual intelligence.
