import json
import os
from unittest.mock import MagicMock, patch

from src.rightsready_pipeline import RightsReadyPipeline


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "fixtures",
)

VALID_FIXTURE_PATH = os.path.join(
    FIXTURES_DIR,
    "project_aurora_valid.json",
)

QUARANTINE_FIXTURE_PATH = os.path.join(
    FIXTURES_DIR,
    "project_aurora_quarantine_test.json",
)


def load_payload():
    with open(
        VALID_FIXTURE_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def ready_validation_result():
    return {
        "status": "READY",
        "checksum_sha256": "test-checksum",
        "normalized_payload": load_payload(),
        "issues": [],
    }


def test_quarantined_package_stops_before_clearance_and_ingestion():
    pipeline = RightsReadyPipeline(
        QUARANTINE_FIXTURE_PATH
    )

    with patch(
        "src.rightsready_pipeline.ClearanceEngine"
    ) as clearance_mock, patch(
        "src.rightsready_pipeline.TrustedIngestionService"
    ) as ingestion_mock:
        result = pipeline.process()

    assert result["status"] == "BLOCKED"
    assert result["validation_status"] == "QUARANTINED"
    assert result["clearance_status"] == "NOT_EVALUATED"
    assert result["ingestion_status"] == "NOT_ATTEMPTED"

    clearance_mock.assert_not_called()
    ingestion_mock.assert_not_called()


@patch(
    "src.rightsready_pipeline.IntakeValidator"
)
@patch(
    "src.rightsready_pipeline.ClearanceEngine"
)
@patch(
    "src.rightsready_pipeline.TrustedIngestionService"
)
def test_cleared_and_ingested_package_is_ready(
    ingestion_class,
    clearance_class,
    validator_class,
):
    validator = MagicMock()
    validator.validate.return_value = (
        ready_validation_result()
    )
    validator_class.return_value = validator

    clearance = MagicMock()
    clearance.evaluate.return_value = {
        "status": "CLEARED",
        "summary": {
            "total_usages": 5,
            "cleared": 5,
            "not_cleared": 0,
        },
        "decisions": [],
    }
    clearance_class.return_value = clearance

    ingestion = MagicMock()
    ingestion.process.return_value = {
        "status": "INGESTED",
        "inserted": True,
        "batch_id": "BATCH-2026-1049",
    }
    ingestion_class.return_value = ingestion

    result = RightsReadyPipeline(
        VALID_FIXTURE_PATH
    ).process()

    assert result["status"] == "READY"
    assert result["validation_status"] == "READY"
    assert result["clearance_status"] == "CLEARED"
    assert result["ingestion_status"] == "INGESTED"


@patch(
    "src.rightsready_pipeline.IntakeValidator"
)
@patch(
    "src.rightsready_pipeline.ClearanceEngine"
)
@patch(
    "src.rightsready_pipeline.TrustedIngestionService"
)
def test_rights_gap_requires_review_but_still_ingests(
    ingestion_class,
    clearance_class,
    validator_class,
):
    validator = MagicMock()
    validator.validate.return_value = (
        ready_validation_result()
    )
    validator_class.return_value = validator

    clearance = MagicMock()
    clearance.evaluate.return_value = {
        "status": "NOT_CLEARED",
        "summary": {
            "total_usages": 5,
            "cleared": 2,
            "not_cleared": 3,
        },
        "decisions": [],
    }
    clearance_class.return_value = clearance

    ingestion = MagicMock()
    ingestion.process.return_value = {
        "status": "INGESTED",
        "inserted": True,
        "batch_id": "BATCH-2026-1049",
    }
    ingestion_class.return_value = ingestion

    result = RightsReadyPipeline(
        VALID_FIXTURE_PATH
    ).process()

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["clearance_status"] == "NOT_CLEARED"
    assert result["ingestion_status"] == "INGESTED"

    ingestion.process.assert_called_once()


@patch(
    "src.rightsready_pipeline.IntakeValidator"
)
@patch(
    "src.rightsready_pipeline.ClearanceEngine"
)
@patch(
    "src.rightsready_pipeline.TrustedIngestionService"
)
def test_existing_batch_can_still_require_review(
    ingestion_class,
    clearance_class,
    validator_class,
):
    validator = MagicMock()
    validator.validate.return_value = (
        ready_validation_result()
    )
    validator_class.return_value = validator

    clearance = MagicMock()
    clearance.evaluate.return_value = {
        "status": "NOT_CLEARED",
        "summary": {
            "total_usages": 5,
            "cleared": 2,
            "not_cleared": 3,
        },
        "decisions": [],
    }
    clearance_class.return_value = clearance

    ingestion = MagicMock()
    ingestion.process.return_value = {
        "status": "ALREADY_INGESTED",
        "inserted": False,
        "batch_id": "BATCH-2026-1049",
    }
    ingestion_class.return_value = ingestion

    result = RightsReadyPipeline(
        VALID_FIXTURE_PATH
    ).process()

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["ingestion_status"] == "ALREADY_INGESTED"


@patch(
    "src.rightsready_pipeline.IntakeValidator"
)
@patch(
    "src.rightsready_pipeline.ClearanceEngine"
)
@patch(
    "src.rightsready_pipeline.TrustedIngestionService"
)
def test_partial_batch_becomes_pipeline_error(
    ingestion_class,
    clearance_class,
    validator_class,
):
    validator = MagicMock()
    validator.validate.return_value = (
        ready_validation_result()
    )
    validator_class.return_value = validator

    clearance = MagicMock()
    clearance.evaluate.return_value = {
        "status": "CLEARED",
        "summary": {},
        "decisions": [],
    }
    clearance_class.return_value = clearance

    ingestion = MagicMock()
    ingestion.process.return_value = {
        "status": "PARTIAL_BATCH_EXISTS",
        "inserted": False,
        "batch_id": "BATCH-2026-1049",
    }
    ingestion_class.return_value = ingestion

    result = RightsReadyPipeline(
        VALID_FIXTURE_PATH
    ).process()

    assert result["status"] == "ERROR"
    assert (
        result["ingestion_status"]
        == "PARTIAL_BATCH_EXISTS"
    )
