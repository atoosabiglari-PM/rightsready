"""
RightsReady Trusted Ingestion Service
-------------------------------------
Provides a secure gateway between the intake validation layer and the ClickHouse
data warehouse. It enforces a strict governance boundary: no quarantined data
may establish a database connection or attempt ingestion.

It implements complete batch idempotency to prevent duplicated or partial data.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from typing import Any, Dict

import clickhouse_connect

from src.intake_validator import IntakeValidator


class TrustedIngestionService:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.client = None

    def process(self) -> Dict[str, Any]:
        """
        Executes the trusted ingestion pipeline:

        1. Validate
        2. Gatekeep based on status
        3. Connect to data warehouse
        4. Check idempotency
        5. Map and insert
        """

        # ---------------------------------------------------------
        # STEP 1 — DETERMINISTIC VALIDATION
        # ---------------------------------------------------------

        validator = IntakeValidator(self.file_path)
        validation_report = validator.validate()

        # ---------------------------------------------------------
        # STEP 2 — GOVERNANCE BOUNDARY
        # ---------------------------------------------------------
        #
        # CRITICAL:
        # Quarantined packages MUST stop here.
        #
        # No ClickHouse connection is created.
        # No database query is executed.
        # No data is inserted.
        #

        if validation_report["status"] == "QUARANTINED":
            return {
                "status": "BLOCKED",
                "validation_status": "QUARANTINED",
                "inserted": False,
                "reason": "Package failed trusted-data intake validation",
                "issues": validation_report["issues"],
            }

        # ---------------------------------------------------------
        # STEP 3 — TRUSTED DATABASE CONNECTION
        # ---------------------------------------------------------

        self._connect_to_database()

        # At this point the package passed deterministic validation.

        payload = validation_report["normalized_payload"]

        batch_id = payload["metadata"]["batch_id"]

        # ---------------------------------------------------------
        # STEP 4 — EXPECTED BATCH SHAPE
        # ---------------------------------------------------------

        expected_counts = {
            "productions": 1,
            "assets": len(payload.get("assets", [])),
            "licenses": len(payload.get("licenses", [])),
            "asset_usage": len(payload.get("asset_usage", [])),
        }

        # ---------------------------------------------------------
        # STEP 5 — IDEMPOTENCY CHECK
        # ---------------------------------------------------------

        idempotency_state = self._check_idempotency(
            batch_id,
            expected_counts,
        )

        if idempotency_state == "ALREADY_INGESTED":
            return {
                "status": "ALREADY_INGESTED",
                "inserted": False,
                "batch_id": batch_id,
                "reason": (
                    "The complete batch already exists in the warehouse."
                ),
            }

        if idempotency_state == "PARTIAL_BATCH_EXISTS":
            return {
                "status": "PARTIAL_BATCH_EXISTS",
                "inserted": False,
                "batch_id": batch_id,
                "reason": (
                    "Unsafe partial state detected. Batch exists in some "
                    "tables but counts do not match expected payload."
                ),
            }

        # ---------------------------------------------------------
        # STEP 6 — TRUSTED INSERTION
        # ---------------------------------------------------------
        #
        # We only reach this section when:
        #
        # validation == READY
        # AND
        # no batch rows already exist
        #

        self._insert_production(
            payload,
            batch_id,
        )

        self._insert_assets(
            payload,
            batch_id,
        )

        self._insert_licenses(
            payload,
            batch_id,
        )

        self._insert_asset_usage(
            payload,
            batch_id,
        )

        # ---------------------------------------------------------
        # STEP 7 — SUCCESS RESULT
        # ---------------------------------------------------------

        return {
            "status": "INGESTED",
            "validation_status": "READY",
            "inserted": True,
            "batch_id": batch_id,
            "checksum_sha256": validation_report["checksum_sha256"],
            "row_counts": expected_counts,
        }

    # =============================================================
    # DATABASE CONNECTION
    # =============================================================

    def _connect_to_database(self):
        """
        Creates the ClickHouse connection securely using
        environment variables.

        No credentials are hard-coded in the application.
        """

        required_vars = [
            "CLICKHOUSE_HOST",
            "CLICKHOUSE_USER",
            "CLICKHOUSE_PASSWORD",
            "CLICKHOUSE_DATABASE",
        ]

        missing = [
            variable
            for variable in required_vars
            if not os.environ.get(variable)
        ]

        if missing:
            raise ValueError(
                "Missing required connection environment variables: "
                + ", ".join(missing)
            )

        self.client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            username=os.environ["CLICKHOUSE_USER"],
            password=os.environ["CLICKHOUSE_PASSWORD"],
            database=os.environ["CLICKHOUSE_DATABASE"],
            secure=True,
        )

    # =============================================================
    # IDEMPOTENCY
    # =============================================================

    def _check_idempotency(
        self,
        batch_id: str,
        expected_counts: Dict[str, int],
    ) -> str:
        """
        Determines whether a batch is:

        READY_TO_INSERT
        ALREADY_INGESTED
        PARTIAL_BATCH_EXISTS

        Batch ID values are passed as parameters rather than interpolated
        directly into SQL.
        """

        tables = [
            "productions",
            "assets",
            "licenses",
            "asset_usage",
        ]

        db_counts = {}

        for table in tables:
            query = (
                f"SELECT count() "
                f"FROM {table} "
                f"WHERE batch_id = {{b:String}}"
            )

            result = self.client.command(
                query,
                parameters={
                    "b": batch_id,
                },
            )

            db_counts[table] = int(result)

        total_db_rows = sum(
            db_counts.values()
        )

        # ---------------------------------------------------------
        # No rows exist
        # ---------------------------------------------------------

        if total_db_rows == 0:
            return "READY_TO_INSERT"

        # ---------------------------------------------------------
        # Complete batch already exists
        # ---------------------------------------------------------

        if db_counts == expected_counts:
            return "ALREADY_INGESTED"

        # ---------------------------------------------------------
        # Something exists, but the batch is incomplete
        # ---------------------------------------------------------

        return "PARTIAL_BATCH_EXISTS"

    # =============================================================
    # PRODUCTION INSERT
    # =============================================================

    def _insert_production(
        self,
        payload: Dict[str, Any],
        batch_id: str,
    ):
        prod = payload["production"]
        meta = payload["metadata"]

        # ClickHouse Date columns require Python date objects.

        release_date_string = prod.get(
            "release_date"
        )

        release_date = (
            date.fromisoformat(
                release_date_string
            )
            if release_date_string
            else None
        )

        columns = [
            "production_id",
            "title",
            "production_type",
            "release_date",
            "requested_territories",
            "distribution_scope",
            "status",
            "source_system",
            "batch_id",
            "schema_version",
        ]

        row = [
            prod["production_id"],
            prod["title"],
            prod["production_type"],
            release_date,
            prod["requested_territories"],
            prod["distribution_scope"],
            prod["status"],
            meta["source_system"],
            batch_id,
            meta["schema_version"],
        ]

        self.client.insert(
            "productions",
            [row],
            column_names=columns,
        )

    # =============================================================
    # ASSET INSERT
    # =============================================================

    def _insert_assets(
        self,
        payload: Dict[str, Any],
        batch_id: str,
    ):
        columns = [
            "asset_id",
            "title",
            "asset_type",
            "rights_holder",
            "description",
            "source_file",
            "source_row",
            "source_system",
            "created_at",
            "batch_id",
        ]

        rows = []

        for asset in payload.get(
            "assets",
            [],
        ):
            asset_metadata = asset[
                "metadata"
            ]

            # ClickHouse DateTime expects Python datetime objects.
            #
            # Example:
            # 2026-08-15T10:30:00Z
            #
            # becomes an offset-aware Python datetime.

            created_at = datetime.fromisoformat(
                asset_metadata[
                    "created_at"
                ].replace(
                    "Z",
                    "+00:00",
                )
            )

            rows.append(
                [
                    asset["asset_id"],
                    asset["title"],
                    asset["asset_type"],
                    asset["rights_holder"],
                    asset["description"],
                    asset_metadata["source_file"],
                    asset_metadata.get(
                        "source_row",
                        0,
                    ),
                    asset_metadata[
                        "source_system"
                    ],
                    created_at,
                    batch_id,
                ]
            )

        if rows:
            self.client.insert(
                "assets",
                rows,
                column_names=columns,
            )

    # =============================================================
    # LICENSE INSERT
    # =============================================================

    def _insert_licenses(
        self,
        payload: Dict[str, Any],
        batch_id: str,
    ):
        columns = [
            "license_id",
            "asset_id",
            "license_type",
            "valid_from",
            "valid_until",
            "permitted_territories",
            "permitted_usage",
            "rights_holder",
            "contract_reference",
            "license_status",
            "batch_id",
        ]

        rows = []

        for license_record in payload.get(
            "licenses",
            [],
        ):
            valid_from_string = (
                license_record.get(
                    "valid_from"
                )
            )

            valid_until_string = (
                license_record.get(
                    "valid_until"
                )
            )

            valid_from = (
                date.fromisoformat(
                    valid_from_string
                )
                if valid_from_string
                else None
            )

            valid_until = (
                date.fromisoformat(
                    valid_until_string
                )
                if valid_until_string
                else None
            )

            rows.append(
                [
                    license_record[
                        "license_id"
                    ],
                    license_record[
                        "asset_id"
                    ],
                    license_record[
                        "license_type"
                    ],
                    valid_from,
                    valid_until,
                    license_record[
                        "permitted_territories"
                    ],
                    license_record[
                        "permitted_usage"
                    ],
                    license_record[
                        "rights_holder"
                    ],
                    license_record[
                        "contract_reference"
                    ],
                    license_record[
                        "license_status"
                    ],
                    batch_id,
                ]
            )

        if rows:
            self.client.insert(
                "licenses",
                rows,
                column_names=columns,
            )

    # =============================================================
    # ASSET USAGE INSERT
    # =============================================================

    def _insert_asset_usage(
        self,
        payload: Dict[str, Any],
        batch_id: str,
    ):
        columns = [
            "usage_id",
            "production_id",
            "asset_id",
            "scene_number",
            "usage_type",
            "duration_seconds",
            "prominence",
            "notes",
            "batch_id",
        ]

        rows = []

        for usage in payload.get(
            "asset_usage",
            [],
        ):
            rows.append(
                [
                    usage["usage_id"],
                    usage["production_id"],
                    usage["asset_id"],
                    usage.get(
                        "scene_number",
                        "",
                    ),
                    usage["usage_type"],
                    usage[
                        "duration_seconds"
                    ],
                    usage["prominence"],
                    usage.get(
                        "notes",
                        "",
                    ),
                    batch_id,
                ]
            )

        if rows:
            self.client.insert(
                "asset_usage",
                rows,
                column_names=columns,
            )


# =============================================================
# COMMAND LINE ENTRY POINT
# =============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "RightsReady Trusted "
            "Ingestion Service"
        )
    )

    parser.add_argument(
        "file",
        help=(
            "Path to the JSON "
            "rights package"
        ),
    )

    args = parser.parse_args()

    service = TrustedIngestionService(
        args.file
    )

    try:
        result = service.process()

        status = result.get(
            "status",
            "UNKNOWN",
        )

        if status == "INGESTED":
            print(
                "\n✅ [SUCCESS] "
                f"Package {status}\n"
            )

        elif status == "BLOCKED":
            print(
                "\n🚫 [REJECTED] "
                f"Package {status} "
                "(Governance Boundary "
                "Enforced)\n"
            )

        elif status == "ALREADY_INGESTED":
            print(
                "\nℹ️ [SKIPPED] "
                f"Batch {status}\n"
            )

        elif status == "PARTIAL_BATCH_EXISTS":
            print(
                "\n⚠️ [ERROR] "
                f"{status} - "
                "Requires manual review\n"
            )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        # Failure states return a non-zero process exit code
        # so automation/CI pipelines can detect them.

        if status in [
            "BLOCKED",
            "PARTIAL_BATCH_EXISTS",
        ]:
            sys.exit(1)

    except ValueError as error:
        print(
            "\n❌ [CONFIGURATION ERROR] "
            f"{str(error)}\n"
        )

        sys.exit(1)