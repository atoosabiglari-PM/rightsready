# Setup

## Prerequisites

- Python 3.12+
- Google Cloud project with Vertex AI enabled
- Access to the configured Vertex AI Agent Engine
- ClickHouse access for warehouse intelligence
- Required Google Cloud authentication configured

## Local Installation

Clone the repository and enter the project directory:

```bash
git clone https://github.com/atoosabiglari-PM/rightsready.git
cd rightsready
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Configuration

```bash
export GOOGLE_CLOUD_PROJECT=rightsready-507619
export GOOGLE_CLOUD_LOCATION=us-central1
export RIGHTSREADY_AGENT_ENGINE_RESOURCE=projects/550358050067/locations/us-central1/reasoningEngines/7030670423406673920
```

## Run Locally

```bash
uvicorn src.web_app:app --host 0.0.0.0 --port 8080
```

Verify the service:

```bash
curl http://localhost:8080/health
```

Expected response: `{"status":"healthy"}`

## Production Deployment

RightsReady is deployed on Google Cloud Run.

Live application: https://rightsready-web-550358050067.us-central1.run.app

## Documentation

- [Architecture](architecture.md)
- [Security & Governance](security-governance.md)
- [Competition Evidence](competition-evidence/README.md)
