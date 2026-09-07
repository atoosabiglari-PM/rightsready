import os
import unittest
import importlib
from unittest.mock import patch, MagicMock
import src.deploy_agent_engine
from google.cloud.aiplatform_v1.types.env_var import SecretRef
from src.adk_app import app as adk_app_instance

class TestAgentEngineDeployment(unittest.TestCase):

    def test_deployment_config_values(self):
        # A: Verify all explicit deployment configuration
        config = src.deploy_agent_engine.get_deployment_config()
        env = config["env_vars"]

        self.assertNotIn("GOOGLE_CLOUD_PROJECT", env)
        self.assertNotIn("GOOGLE_CLOUD_LOCATION", env)
        self.assertEqual(env["GOOGLE_GENAI_USE_VERTEXAI"], "TRUE")

        self.assertEqual(env["CLICKHOUSE_HOST"], "sjhhz2rarh.us-central1.gcp.clickhouse.cloud")
        self.assertEqual(env["CLICKHOUSE_USER"], "default")
        self.assertEqual(env["CLICKHOUSE_DATABASE"], "rightsready")
        self.assertEqual(env["CLICKHOUSE_SECURE"], "true")
        self.assertEqual(env["CLICKHOUSE_VERIFY"], "true")
        self.assertEqual(env["CLICKHOUSE_ALLOW_WRITE_ACCESS"], "false")
        self.assertEqual(env["CLICKHOUSE_MCP_SERVER_TRANSPORT"], "stdio")

        self.assertNotIn("MCP_CLICKHOUSE_EXECUTABLE", env)
        self.assertEqual(env["HTTPS_PROXY"], "http://10.10.1.2:3128")

        password_secret = env["CLICKHOUSE_PASSWORD"]
        self.assertIsInstance(password_secret, SecretRef)
        self.assertEqual(password_secret.secret, "rightsready-clickhouse-password")
        self.assertEqual(password_secret.version, "latest")

        self.assertEqual(config["requirements"], "requirements.txt")
        self.assertEqual(config["display_name"], "RightsReady")
        self.assertEqual(config["description"], "Governed media rights clearance agent using Google ADK, Gemini, deterministic clearance tools, and ClickHouse MCP.")
        self.assertEqual(config["extra_packages"], ["src", "data"])
        self.assertEqual(config["service_account"], "rightsready-agent-runtime@rightsready-507619.iam.gserviceaccount.com")
        self.assertEqual(config["psc_interface_config"].network_attachment, "projects/rightsready-507619/regions/us-central1/networkAttachments/rightsready-agent-attachment")

    @patch("src.deploy_agent_engine.create")
    @patch("src.deploy_agent_engine.vertexai.init")
    @patch("src.deploy_agent_engine.AdkApp")
    def test_deployment_config_is_side_effect_free(self, mock_adk_app, mock_init, mock_create):
        # B: Verify get_deployment_config() is side-effect-free
        src.deploy_agent_engine.get_deployment_config()
        
        mock_adk_app.assert_not_called()
        mock_init.assert_not_called()
        mock_create.assert_not_called()

    @patch("src.deploy_agent_engine.create")
    @patch("src.deploy_agent_engine.vertexai.init")
    @patch("src.deploy_agent_engine.AdkApp")
    def test_deploy_execution(self, mock_adk_app, mock_init, mock_create):
        # C: Strengthen deploy() test
        with patch.dict(os.environ, {"RIGHTSREADY_STAGING_BUCKET": "gs://test-bucket"}):
            mock_managed_app = MagicMock()
            mock_adk_app.return_value = mock_managed_app
            
            src.deploy_agent_engine.deploy()
            
            mock_init.assert_called_once_with(
                project="rightsready-507619",
                location="us-central1",
                staging_bucket="gs://test-bucket"
            )
            
            mock_adk_app.assert_called_once_with(app=adk_app_instance)
            mock_create.assert_called_once()
            
            args, kwargs = mock_create.call_args
            self.assertEqual(kwargs["agent_engine"], mock_managed_app)
            # Verify other config values are passed to create
            self.assertEqual(kwargs["display_name"], "RightsReady")

    def test_deploy_missing_bucket(self):
        # D: Verify missing staging bucket behavior
        with patch("src.deploy_agent_engine.vertexai.init") as mock_init, \
             patch("src.deploy_agent_engine.AdkApp") as mock_adk_app, \
             patch("src.deploy_agent_engine.create") as mock_create, \
             patch.dict(os.environ, {}, clear=True):
             
            with self.assertRaises(ValueError) as cm:
                src.deploy_agent_engine.deploy()
            self.assertEqual(str(cm.exception), "RIGHTSREADY_STAGING_BUCKET environment variable must be set.")
            
            mock_init.assert_not_called()
            mock_adk_app.assert_not_called()
            mock_create.assert_not_called()

    def test_import_side_effects(self):
        # E: REAL import-side-effect test
        with patch("src.deploy_agent_engine.vertexai.init") as mock_init, \
             patch("src.deploy_agent_engine.AdkApp") as mock_adk_app, \
             patch("src.deploy_agent_engine.create") as mock_create:
            
            importlib.reload(src.deploy_agent_engine)
            
            mock_init.assert_not_called()
            mock_adk_app.assert_not_called()
            mock_create.assert_not_called()

    def test_requirements_pinning(self):
        # F: Verify strict requirement pinning
        with open("requirements.txt", "r") as f:
            lines = [line.strip() for line in f.readlines()]

        self.assertIn("google-cloud-aiplatform[agent_engines]==1.163.0", lines)
        self.assertIn("google-adk==2.6.2", lines)

        # Verify rejection of looser bounds
        self.assertNotIn("google-cloud-aiplatform[agent_engines]>=1.160.0", lines)
        self.assertNotIn("google-adk>=2.6.2", lines)


if __name__ == "__main__":
    unittest.main()
