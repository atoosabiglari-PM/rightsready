"""
RightsReady End-to-End Pipeline
-------------------------------
Coordinates the complete RightsReady workflow:

1. Deterministic intake validation
2. Governance boundary enforcement
3. Deterministic clearance evaluation
4. Trusted ClickHouse ingestion
5. Unified pipeline result

Validation and clearance are intentionally separate concepts.

A package may contain structurally trusted data while still having rights
clearance gaps. Clearance gaps therefore do not prevent trusted ingestion;
they produce a REVIEW_REQUIRED business status.
"""

import argparse
import json
import sys
from typing import Any, Dict

from src.clearance_engine import ClearanceEngine
from src.intake_validator import IntakeValidator
from src.trusted_ingestion import TrustedIngestionService


class RightsReadyPipeline:
    """
    Coordinate validation, clearance evaluation, and trusted ingestion.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def process(self) -> Dict[str, Any]:
        """
        Execute the complete RightsReady pipeline.
        """

        # =========================================================
        # STEP 1 — DETERMINISTIC VALIDATION
        # =========================================================

        validator = IntakeValidator(
            self.file_path
        )

        validation_result = validator.validate()

        validation_status = validation_result.get(
            "status",
            "UNKNOWN",
        )

        # =========================================================
        # STEP 2 — GOVERNANCE BOUNDARY
        # =========================================================
        #
        # Quarantined data stops here.
        #
        # No clearance decision is trusted.
        # No ClickHouse connection is created.
        # No ingestion is attempted.
        #

        if validation_status == "QUARANTINED":
            return {
                "status": "BLOCKED",
                "stage": "VALIDATION",
                "validation_status": (
                    validation_status
                ),
                "clearance_status": (
                    "NOT_EVALUATED"
                ),
                "ingestion_status": (
                    "NOT_ATTEMPTED"
                ),
                "checksum_sha256": (
                    validation_result.get(
                        "checksum_sha256"
                    )
                ),
                "issues": validation_result.get(
                    "issues",
                    [],
                ),
            }

        # =========================================================
        # STEP 3 — CLEARANCE EVALUATION
        # =========================================================

        normalized_payload = (
            validation_result[
                "normalized_payload"
            ]
        )

        clearance_engine = ClearanceEngine(
            normalized_payload
        )

        clearance_result = (
            clearance_engine.evaluate()
        )

        clearance_status = (
            clearance_result.get(
                "status",
                "UNKNOWN",
            )
        )

        # =========================================================
        # STEP 4 — TRUSTED INGESTION
        # =========================================================
        #
        # Clearance gaps do NOT block ingestion.
        #
        # RightsReady still needs trusted records in the warehouse
        # so unresolved rights issues can be tracked and reviewed.
        #

        ingestion_service = (
            TrustedIngestionService(
                self.file_path
            )
        )

        ingestion_result = (
            ingestion_service.process()
        )

        ingestion_status = (
            ingestion_result.get(
                "status",
                "UNKNOWN",
            )
        )

        # =========================================================
        # STEP 5 — UNIFIED BUSINESS STATUS
        # =========================================================

        if ingestion_status == (
            "PARTIAL_BATCH_EXISTS"
        ):
            pipeline_status = "ERROR"

        elif ingestion_status == "BLOCKED":
            pipeline_status = "BLOCKED"

        elif ingestion_status in {
            "INGESTED",
            "ALREADY_INGESTED",
        }:
            if clearance_status == "CLEARED":
                pipeline_status = "READY"
            else:
                pipeline_status = (
                    "REVIEW_REQUIRED"
                )

        else:
            pipeline_status = "ERROR"

        # =========================================================
        # STEP 6 — UNIFIED RESULT
        # =========================================================

        return {
            "status": pipeline_status,
            "validation_status": (
                validation_status
            ),
            "clearance_status": (
                clearance_status
            ),
            "ingestion_status": (
                ingestion_status
            ),
            "batch_id": (
                normalized_payload
                .get("metadata", {})
                .get("batch_id")
            ),
            "production_id": (
                normalized_payload
                .get("production", {})
                .get("production_id")
            ),
            "checksum_sha256": (
                validation_result.get(
                    "checksum_sha256"
                )
            ),
            "clearance": clearance_result,
            "ingestion": ingestion_result,
        }


# =============================================================
# COMMAND LINE ENTRY POINT
# =============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete RightsReady "
            "validation, clearance, and "
            "trusted-ingestion pipeline."
        )
    )

    parser.add_argument(
        "file",
        help=(
            "Path to a RightsReady JSON "
            "rights package"
        ),
    )

    args = parser.parse_args()

    try:
        pipeline = RightsReadyPipeline(
            args.file
        )

        result = pipeline.process()

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        status = result.get(
            "status",
            "ERROR",
        )

        if status == "BLOCKED":
            sys.exit(1)

        if status == "ERROR":
            sys.exit(1)

        if status == "REVIEW_REQUIRED":
            sys.exit(2)

        sys.exit(0)

    except ValueError as error:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "stage": "CONFIGURATION",
                    "message": str(error),
                },
                indent=2,
            )
        )

        sys.exit(1)

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "stage": "PIPELINE",
                    "error_type": (
                        type(error).__name__
                    ),
                    "message": str(error),
                },
                indent=2,
            )
        )

        sys.exit(1)
