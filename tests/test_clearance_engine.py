import json
import os

from src.clearance_engine import ClearanceEngine


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


def load_payload():
    with open(
        VALID_FIXTURE_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_decision(result, usage_id):
    return next(
        decision
        for decision in result["decisions"]
        if decision["usage_id"] == usage_id
    )


def test_aurora_clearance_summary():
    result = ClearanceEngine(
        load_payload()
    ).evaluate()

    assert result["status"] == "NOT_CLEARED"
    assert result["summary"] == {
        "total_usages": 5,
        "cleared": 2,
        "not_cleared": 3,
    }


def test_detects_worldwide_territory_gap():
    result = ClearanceEngine(
        load_payload()
    ).evaluate()

    decision = get_decision(
        result,
        "USG-001",
    )

    assert decision["status"] == "NOT_CLEARED"
    assert "TERRITORY_GAP" in decision["reason_codes"]


def test_detects_expired_license():
    result = ClearanceEngine(
        load_payload()
    ).evaluate()

    decision = get_decision(
        result,
        "USG-002",
    )

    assert decision["status"] == "NOT_CLEARED"
    assert "LICENSE_EXPIRED" in decision["reason_codes"]


def test_detects_unpermitted_usage():
    result = ClearanceEngine(
        load_payload()
    ).evaluate()

    decision = get_decision(
        result,
        "USG-003",
    )

    assert decision["status"] == "NOT_CLEARED"
    assert "USAGE_NOT_PERMITTED" in decision["reason_codes"]


def test_clears_valid_work_for_hire_asset():
    result = ClearanceEngine(
        load_payload()
    ).evaluate()

    decision = get_decision(
        result,
        "USG-004",
    )

    assert decision["status"] == "CLEARED"
    assert decision["matched_license_id"] == "LIC-004"


def test_clears_owned_ip_asset():
    result = ClearanceEngine(
        load_payload()
    ).evaluate()

    decision = get_decision(
        result,
        "USG-005",
    )

    assert decision["status"] == "CLEARED"
    assert decision["matched_license_id"] == "LIC-005"


def test_missing_license_is_not_cleared():
    payload = load_payload()

    payload["licenses"] = [
        license_record
        for license_record in payload["licenses"]
        if license_record["asset_id"] != "AST-005"
    ]

    result = ClearanceEngine(
        payload
    ).evaluate()

    decision = get_decision(
        result,
        "USG-005",
    )

    assert decision["status"] == "NOT_CLEARED"
    assert decision["reason_codes"] == [
        "NO_LICENSE"
    ]
