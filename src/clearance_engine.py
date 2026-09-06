"""
RightsReady Clearance Decision Engine
-------------------------------------
Deterministically evaluates whether each asset usage is cleared for a planned
production based on:

1. License execution status
2. License validity dates
3. Territory coverage
4. Permitted usage

No LLM is used for clearance decisions.
"""

import argparse
import json
import sys
from datetime import date
from typing import Any, Dict, List, Optional


class ClearanceEngine:
    """
    Evaluate a normalized RightsReady package and determine whether each
    asset usage is cleared by at least one valid license.
    """

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload

        self.production = payload.get("production", {})
        self.assets = payload.get("assets", [])
        self.licenses = payload.get("licenses", [])
        self.asset_usage = payload.get("asset_usage", [])

        self.assets_by_id = {
            asset.get("asset_id"): asset
            for asset in self.assets
            if asset.get("asset_id")
        }

        self.licenses_by_asset: Dict[str, List[Dict[str, Any]]] = {}

        for license_record in self.licenses:
            asset_id = license_record.get("asset_id")

            if asset_id:
                self.licenses_by_asset.setdefault(
                    asset_id,
                    [],
                ).append(license_record)

    # =============================================================
    # PUBLIC API
    # =============================================================

    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate every asset usage in the package.

        Returns:
            {
                "status": "CLEARED" | "NOT_CLEARED",
                "production_id": "...",
                "summary": {...},
                "decisions": [...]
            }
        """

        decisions = [
            self._evaluate_usage(usage)
            for usage in self.asset_usage
        ]

        cleared_count = sum(
            1
            for decision in decisions
            if decision["status"] == "CLEARED"
        )

        not_cleared_count = (
            len(decisions) - cleared_count
        )

        overall_status = (
            "CLEARED"
            if not_cleared_count == 0
            else "NOT_CLEARED"
        )

        return {
            "status": overall_status,
            "production_id": self.production.get(
                "production_id"
            ),
            "production_title": self.production.get(
                "title"
            ),
            "summary": {
                "total_usages": len(decisions),
                "cleared": cleared_count,
                "not_cleared": not_cleared_count,
            },
            "decisions": decisions,
        }

    # =============================================================
    # USAGE EVALUATION
    # =============================================================

    def _evaluate_usage(
        self,
        usage: Dict[str, Any],
    ) -> Dict[str, Any]:
        asset_id = usage.get("asset_id")
        usage_id = usage.get("usage_id")

        asset = self.assets_by_id.get(asset_id)

        if asset is None:
            return self._failed_decision(
                usage,
                reason_code="ASSET_NOT_FOUND",
                message=(
                    f"Asset {asset_id} does not exist "
                    "in the package."
                ),
            )

        candidate_licenses = self.licenses_by_asset.get(
            asset_id,
            [],
        )

        if not candidate_licenses:
            return self._failed_decision(
                usage,
                reason_code="NO_LICENSE",
                message=(
                    f"No license exists for asset "
                    f"{asset_id}."
                ),
            )

        license_evaluations = []

        for license_record in candidate_licenses:
            evaluation = self._evaluate_license(
                usage,
                license_record,
            )

            license_evaluations.append(evaluation)

            if evaluation["eligible"]:
                return {
                    "usage_id": usage_id,
                    "asset_id": asset_id,
                    "asset_title": asset.get("title"),
                    "usage_type": usage.get("usage_type"),
                    "status": "CLEARED",
                    "matched_license_id": (
                        license_record.get("license_id")
                    ),
                    "reason_codes": [],
                    "messages": [],
                    "license_evaluations": (
                        license_evaluations
                    ),
                }

        reason_codes = []
        messages = []

        for evaluation in license_evaluations:
            for reason in evaluation["reasons"]:
                code = reason["code"]
                message = reason["message"]

                if code not in reason_codes:
                    reason_codes.append(code)

                if message not in messages:
                    messages.append(message)

        return {
            "usage_id": usage_id,
            "asset_id": asset_id,
            "asset_title": asset.get("title"),
            "usage_type": usage.get("usage_type"),
            "status": "NOT_CLEARED",
            "matched_license_id": None,
            "reason_codes": reason_codes,
            "messages": messages,
            "license_evaluations": license_evaluations,
        }

    # =============================================================
    # LICENSE EVALUATION
    # =============================================================

    def _evaluate_license(
        self,
        usage: Dict[str, Any],
        license_record: Dict[str, Any],
    ) -> Dict[str, Any]:
        reasons = []

        self._check_license_status(
            license_record,
            reasons,
        )

        self._check_license_dates(
            license_record,
            reasons,
        )

        self._check_territories(
            license_record,
            reasons,
        )

        self._check_usage_permission(
            usage,
            license_record,
            reasons,
        )

        return {
            "license_id": license_record.get(
                "license_id"
            ),
            "eligible": len(reasons) == 0,
            "reasons": reasons,
        }

    # =============================================================
    # RULE 1 — LICENSE STATUS
    # =============================================================

    def _check_license_status(
        self,
        license_record: Dict[str, Any],
        reasons: List[Dict[str, str]],
    ) -> None:
        status = str(
            license_record.get(
                "license_status",
                "",
            )
        ).strip().lower()

        if status != "executed":
            reasons.append(
                {
                    "code": "LICENSE_NOT_EXECUTED",
                    "message": (
                        "License is not in executed status."
                    ),
                }
            )

    # =============================================================
    # RULE 2 — DATE VALIDITY
    # =============================================================

    def _check_license_dates(
        self,
        license_record: Dict[str, Any],
        reasons: List[Dict[str, str]],
    ) -> None:
        release_date_string = self.production.get(
            "release_date"
        )

        valid_from_string = license_record.get(
            "valid_from"
        )

        valid_until_string = license_record.get(
            "valid_until"
        )

        if not release_date_string:
            reasons.append(
                {
                    "code": "MISSING_RELEASE_DATE",
                    "message": (
                        "Production release date is missing."
                    ),
                }
            )
            return

        try:
            release_date = date.fromisoformat(
                release_date_string
            )
        except ValueError:
            reasons.append(
                {
                    "code": "INVALID_RELEASE_DATE",
                    "message": (
                        "Production release date is invalid."
                    ),
                }
            )
            return

        valid_from = self._parse_optional_date(
            valid_from_string
        )

        valid_until = self._parse_optional_date(
            valid_until_string
        )

        if (
            valid_from_string
            and valid_from is None
        ):
            reasons.append(
                {
                    "code": "INVALID_LICENSE_START_DATE",
                    "message": (
                        "License valid_from date is invalid."
                    ),
                }
            )

        if (
            valid_until_string
            and valid_until is None
        ):
            reasons.append(
                {
                    "code": "INVALID_LICENSE_END_DATE",
                    "message": (
                        "License valid_until date is invalid."
                    ),
                }
            )

        if valid_from and release_date < valid_from:
            reasons.append(
                {
                    "code": "LICENSE_NOT_YET_VALID",
                    "message": (
                        "License does not begin until "
                        f"{valid_from.isoformat()}, after the "
                        "production release date."
                    ),
                }
            )

        if valid_until and release_date > valid_until:
            reasons.append(
                {
                    "code": "LICENSE_EXPIRED",
                    "message": (
                        "License expires on "
                        f"{valid_until.isoformat()}, before the "
                        "production release date."
                    ),
                }
            )

    # =============================================================
    # RULE 3 — TERRITORY COVERAGE
    # =============================================================

    def _check_territories(
        self,
        license_record: Dict[str, Any],
        reasons: List[Dict[str, str]],
    ) -> None:
        requested = {
            str(territory).strip().upper()
            for territory in self.production.get(
                "requested_territories",
                [],
            )
        }

        permitted = {
            str(territory).strip().upper()
            for territory in license_record.get(
                "permitted_territories",
                [],
            )
        }

        if not requested:
            reasons.append(
                {
                    "code": "NO_REQUESTED_TERRITORIES",
                    "message": (
                        "Production has no requested territories."
                    ),
                }
            )
            return

        # WORLDWIDE on the license covers every requested territory.
        if "WORLDWIDE" in permitted:
            return

        # A worldwide production requires worldwide license coverage.
        if "WORLDWIDE" in requested:
            reasons.append(
                {
                    "code": "TERRITORY_GAP",
                    "message": (
                        "Production requests worldwide rights, "
                        "but the license is not worldwide."
                    ),
                }
            )
            return

        missing = sorted(
            requested - permitted
        )

        if missing:
            reasons.append(
                {
                    "code": "TERRITORY_GAP",
                    "message": (
                        "License does not cover requested "
                        "territories: "
                        + ", ".join(missing)
                    ),
                }
            )

    # =============================================================
    # RULE 4 — USAGE PERMISSION
    # =============================================================

    def _check_usage_permission(
        self,
        usage: Dict[str, Any],
        license_record: Dict[str, Any],
        reasons: List[Dict[str, str]],
    ) -> None:
        usage_type = str(
            usage.get(
                "usage_type",
                "",
            )
        ).strip().lower()

        permitted_usage = {
            str(item).strip().lower()
            for item in license_record.get(
                "permitted_usage",
                [],
            )
        }

        if "all_media" in permitted_usage:
            return

        if usage_type not in permitted_usage:
            reasons.append(
                {
                    "code": "USAGE_NOT_PERMITTED",
                    "message": (
                        f"Usage type '{usage_type}' is not "
                        "permitted by this license."
                    ),
                }
            )

    # =============================================================
    # HELPERS
    # =============================================================

    @staticmethod
    def _parse_optional_date(
        value: Optional[str],
    ) -> Optional[date]:
        if not value:
            return None

        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _failed_decision(
        self,
        usage: Dict[str, Any],
        reason_code: str,
        message: str,
    ) -> Dict[str, Any]:
        asset_id = usage.get("asset_id")
        asset = self.assets_by_id.get(
            asset_id,
            {},
        )

        return {
            "usage_id": usage.get("usage_id"),
            "asset_id": asset_id,
            "asset_title": asset.get("title"),
            "usage_type": usage.get("usage_type"),
            "status": "NOT_CLEARED",
            "matched_license_id": None,
            "reason_codes": [
                reason_code,
            ],
            "messages": [
                message,
            ],
            "license_evaluations": [],
        }


# =============================================================
# COMMAND LINE ENTRY POINT
# =============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "RightsReady deterministic rights "
            "clearance decision engine"
        )
    )

    parser.add_argument(
        "file",
        help=(
            "Path to a normalized RightsReady "
            "JSON package"
        ),
    )

    args = parser.parse_args()

    try:
        with open(
            args.file,
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        engine = ClearanceEngine(payload)
        result = engine.evaluate()

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        if result["status"] != "CLEARED":
            sys.exit(1)

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "message": str(error),
                },
                indent=2,
            )
        )
        sys.exit(1)
