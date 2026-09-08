# Devpost Submission Draft

## Project Title
RightsReady

## Tagline
AI rights-clearance control center for film and media production.

## Inspiration / Problem
Film and media production teams require rapid, accurate rights clearance. Relying solely on AI for legal clearance decisions is dangerous, as AI can hallucinate.

## What it does
RightsReady acts as a control center. Gemini orchestrates the workflow, while deterministic tools make authoritative, governed clearance decisions. ClickHouse provides live warehouse intelligence via MCP.

## How we built it
- **Orchestration:** Vertex AI Agent Engine with Gemini/ADK.
- **Backend:** FastAPI.
- **Intelligence:** ClickHouse with MCP tools.
- **Deployment:** Google Cloud Run.

## Google Cloud technologies used
Cloud Run, Vertex AI, Agent Engine.

## ClickHouse usage
Live warehouse intelligence queryable through MCP.

## How Gemini is used
Gemini orchestrates user requests, interprets warehouse queries, and provides explanations for clearance decisions made by deterministic tools.

## How deterministic governance works
The `deterministic_clearance` tool applies business rules to license and asset data, ensuring legal decisions are predictable and governed.

## Public Demo URL
https://rightsready-web-550358050067.us-central1.run.app

## GitHub Repository
https://github.com/atoosabiglari-PM/rightsready
