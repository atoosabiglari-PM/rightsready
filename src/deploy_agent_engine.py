import os
from vertexai.agent_engines import AdkApp, create
from google.cloud.aiplatform_v1.types.env_var import SecretRef
from google.cloud.aiplatform_v1.types.service_networking import PscInterfaceConfig
import vertexai
from src.adk_app import app

def get_deployment_config():
    """Returns the configuration for the Agent Engine deployment."""
    psc_interface_config = PscInterfaceConfig(
        network_attachment="projects/rightsready-507619/regions/us-central1/networkAttachments/rightsready-agent-attachment"
    )

    env_vars = {
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "CLICKHOUSE_HOST": "sjhhz2rarh.us-central1.gcp.clickhouse.cloud",
        "CLICKHOUSE_USER": "default",
        "CLICKHOUSE_DATABASE": "rightsready",
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_VERIFY": "true",
        "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",
        "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
        "HTTPS_PROXY": "http://10.10.1.2:3128",
        "CLICKHOUSE_PASSWORD": SecretRef(
            secret="rightsready-clickhouse-password",
            version="latest"
        )
    }
    
    return {
        "requirements": "requirements.txt",
        "display_name": "RightsReady",
        "description": "Governed media rights clearance agent using Google ADK, Gemini, deterministic clearance tools, and ClickHouse MCP.",
        "extra_packages": ["src", "data"],
        "env_vars": env_vars,
        "service_account": "rightsready-agent-runtime@rightsready-507619.iam.gserviceaccount.com",
        "psc_interface_config": psc_interface_config
    }

def deploy():
    """Initializes and creates the Agent Engine deployment."""
    staging_bucket = os.environ.get("RIGHTSREADY_STAGING_BUCKET")
    if not staging_bucket:
        raise ValueError("RIGHTSREADY_STAGING_BUCKET environment variable must be set.")
    
    vertexai.init(
        project="rightsready-507619",
        location="us-central1",
        staging_bucket=staging_bucket
    )
    
    managed_app = AdkApp(app=app)
    
    config = get_deployment_config()
    config["agent_engine"] = managed_app
    
    return create(**config)

if __name__ == "__main__":
    print("Deployment triggered by user.")
    deploy()
