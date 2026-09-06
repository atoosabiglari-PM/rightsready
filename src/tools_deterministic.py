from typing import Any, Dict
from src.intake_validator import IntakeValidator
from src.clearance_engine import ClearanceEngine
from src.rightsready_pipeline import RightsReadyPipeline
from src.trusted_ingestion import TrustedIngestionService

def deterministic_validate(file_path: str) -> Dict[str, Any]:
    """
    Deterministically validates a rights package.
    Returns the validation status and issues.
    This is the AUTHORITATIVE source for data quality.
    """
    validator = IntakeValidator(file_path)
    report = validator.validate()
    # Remove large payload for tool response efficiency
    report.pop("normalized_payload", None)
    return report

def deterministic_clearance(file_path: str) -> Dict[str, Any]:
    """
    Deterministically evaluates rights clearance for a package.
    Gemini MUST NOT override these decisions.
    """
    validator = IntakeValidator(file_path)
    val_report = validator.validate()
    
    if val_report["status"] == "QUARANTINED":
        return {
            "status": "BLOCKED",
            "reason": "Validation failed",
            "issues": val_report["issues"]
        }
        
    engine = ClearanceEngine(val_report["normalized_payload"])
    return engine.evaluate()

def deterministic_pipeline_execute(file_path: str) -> Dict[str, Any]:
    """
    Executes the full governed RightsReady pipeline.
    This includes validation, clearance, and trusted ingestion.
    This is the ONLY path for data ingestion.
    """
    pipeline = RightsReadyPipeline(file_path)
    return pipeline.process()
