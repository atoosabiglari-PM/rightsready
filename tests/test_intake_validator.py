"""
RightsReady Intake Validator Tests
----------------------------------
Verifies the deterministic ingestion validation layer using known
synthetic fixtures.
"""

import json
import os
import tempfile

from src.intake_validator import IntakeValidator


# Resolve fixture paths relative to this test file so tests can run
# consistently from the RightsReady repository root.
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


def test_valid_fixture_returns_ready():
    """
    A structurally valid rights package must pass intake validation.

    The package intentionally contains downstream business-rights
    conflicts, but those are NOT intake-data errors.
    """

    validator = IntakeValidator(
        VALID_FIXTURE_PATH
    )

    report = validator.validate()

    assert report["status"] == "READY"

    assert (
        report["checksum_sha256"] != ""
    ), "Checksum must be generated."

    assert "normalized_payload" in report

    # Test-only metadata must never enter normalized business data.
    assert (
        "_test_expectations"
        not in report["normalized_payload"]
    )

    # The valid fixture must have no blocking validation issues.
    critical_issues = [
        issue
        for issue in report["issues"]
        if issue["severity"]
        in ["ERROR", "SECURITY_REVIEW"]
    ]

    assert len(critical_issues) == 0, (
        "Valid fixture raised unexpected critical issues: "
        f"{critical_issues}"
    )


def test_quarantine_fixture_detects_all_issues():
    """
    The deliberately flawed fixture must be quarantined and all major
    validation/security issue classes must be detected.
    """

    validator = IntakeValidator(
        QUARANTINE_FIXTURE_PATH
    )

    report = validator.validate()

    assert report["status"] == "QUARANTINED"
    assert report["issue_count"] > 0

    # Test expectations are test metadata only.
    assert (
        "_test_expectations"
        not in report["normalized_payload"]
    )

    issue_types_found = {
        issue["issue_type"]
        for issue in report["issues"]
    }

    expected_issues = {
        "DUPLICATE_ID",
        "MISSING_REQUIRED_FIELD",
        "INVALID_DATE",
        "INVALID_DATE_RANGE",
        "BROKEN_REFERENCE",
        "INVALID_TERRITORY",
        "POSSIBLE_PROMPT_INJECTION",
        "NORMALIZATION_REQUIRED",
    }

    missing_detections = (
        expected_issues - issue_types_found
    )

    assert not missing_detections, (
        "Validator failed to detect: "
        f"{missing_detections}"
    )

    # Verify normalization of the intentionally messy asset.
    assets = report[
        "normalized_payload"
    ].get(
        "assets",
        [],
    )

    ast_105 = next(
        (
            asset
            for asset in assets
            if isinstance(asset, dict)
            and asset.get("asset_id") == "AST-105"
        ),
        None,
    )

    assert (
        ast_105 is not None
    ), "Target asset for normalization test not found."

    assert (
        ast_105["asset_id"] == "AST-105"
    ), "Asset ID was not normalized correctly."

    assert (
        ast_105["title"]
        == "MESSY casing And WhiTEspace"
    ), "Asset title was not normalized correctly."

    # Verify severity policies.
    for issue in report["issues"]:

        if (
            issue["issue_type"]
            == "POSSIBLE_PROMPT_INJECTION"
        ):
            assert (
                issue["severity"]
                == "SECURITY_REVIEW"
            )

            assert (
                issue["record_id"]
                == "AST-103"
            )

        elif (
            issue["issue_type"]
            == "NORMALIZATION_REQUIRED"
        ):
            assert (
                issue["severity"]
                == "WARNING"
            )

        elif (
            issue["issue_type"]
            == "INVALID_TERRITORY"
        ):
            assert (
                issue["severity"]
                == "ERROR"
            )


def test_malformed_section_types():
    """
    Invalid JSON types at required top-level sections must trigger
    INVALID_STRUCTURE errors without crashing the pipeline.
    """

    malformed_payload = {
        "metadata": [],
        "production": "invalid_string",
        "assets": {},
        "licenses": 123,
        "asset_usage": None,
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        suffix=".json",
    ) as temporary_file:

        json.dump(
            malformed_payload,
            temporary_file,
        )

        temporary_path = (
            temporary_file.name
        )

    try:
        validator = IntakeValidator(
            temporary_path
        )

        report = validator.validate()

        assert (
            report["status"]
            == "QUARANTINED"
        )

        issue_types = [
            issue["issue_type"]
            for issue in report["issues"]
        ]

        assert (
            "INVALID_STRUCTURE"
            in issue_types
        )

        invalid_structure_issues = [
            issue
            for issue in report["issues"]
            if issue["issue_type"]
            == "INVALID_STRUCTURE"
        ]

        # All five required sections have deliberately wrong types.
        assert (
            len(invalid_structure_issues)
            == 5
        )

    finally:
        os.remove(
            temporary_path
        )


def test_invalid_root_type():
    """
    Valid JSON with an array at the root must be safely quarantined.
    """

    malformed_payload = [
        {
            "metadata": {}
        }
    ]

    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        suffix=".json",
    ) as temporary_file:

        json.dump(
            malformed_payload,
            temporary_file,
        )

        temporary_path = (
            temporary_file.name
        )

    try:
        validator = IntakeValidator(
            temporary_path
        )

        report = validator.validate()

        assert (
            report["status"]
            == "QUARANTINED"
        )

        assert (
            len(report["issues"])
            == 1
        )

        assert (
            report["issues"][0][
                "issue_type"
            ]
            == "INVALID_STRUCTURE"
        )

        assert (
            report["issues"][0][
                "record_type"
            ]
            == "root"
        )

        assert (
            report["normalized_payload"]
            == {}
        )

    finally:
        os.remove(
            temporary_path
        )


def test_invalid_collection_element_type():
    """
    Non-object elements inside a valid collection array must be flagged
    as INVALID_STRUCTURE without causing the validator to crash.
    """

    payload = {
        "metadata": {
            "batch_id": "1",
            "source_system": "SYS",
            "source_file": "F",
            "uploaded_at": "D",
            "uploaded_by": "U",
            "schema_version": "1",
        },
        "production": {
            "production_id": "P1",
            "title": "T",
            "production_type": "type",
            "release_date": "2026-01-01",
            "requested_territories": [
                "WORLDWIDE"
            ],
            "distribution_scope": "world",
            "status": "planned",
        },
        "assets": [
            {
                "asset_id": "A1",
                "title": "T1",
                "asset_type": "music",
                "rights_holder": "R1",
                "description": "D1",
            },
            "I am a string, not a dict",
            [
                "I am a list, not a dict"
            ],
        ],
        "licenses": [],
        "asset_usage": [],
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        suffix=".json",
    ) as temporary_file:

        json.dump(
            payload,
            temporary_file,
        )

        temporary_path = (
            temporary_file.name
        )

    try:
        validator = IntakeValidator(
            temporary_path
        )

        report = validator.validate()

        assert (
            report["status"]
            == "QUARANTINED"
        )

        invalid_structure_issues = [
            issue
            for issue in report["issues"]
            if (
                issue["issue_type"]
                == "INVALID_STRUCTURE"
                and issue["record_type"]
                == "assets"
            )
        ]

        # Two malformed collection elements were inserted.
        assert (
            len(invalid_structure_issues)
            == 2
        )

        indices_flagged = {
            issue["record_id"]
            for issue
            in invalid_structure_issues
        }

        assert (
            "index_1"
            in indices_flagged
        )

        assert (
            "index_2"
            in indices_flagged
        )

    finally:
        os.remove(
            temporary_path
        )


def test_missing_file_handling():
    """
    A nonexistent input file must be quarantined gracefully.
    """

    validator = IntakeValidator(
        "non_existent_file.json"
    )

    report = validator.validate()

    assert (
        report["status"]
        == "QUARANTINED"
    )

    assert (
        len(report["issues"])
        == 1
    )

    assert (
        report["issues"][0][
            "issue_type"
        ]
        == "PARSE_ERROR"
    )