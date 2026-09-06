"""
RightsReady Intake Validation Layer
-----------------------------------
This module provides a deterministic, zero-LLM validation pipeline for incoming
media rights clearance packages. It verifies schema structure, referential
integrity, date formats, ISO territories, and flags suspicious inputs.

It produces a sanitized, normalized payload ready for downstream ingestion
into ClickHouse and clearance evaluation.
"""

import json
import hashlib
import re
import copy
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, List

# pycountry is used for deterministic ISO-3166-1 alpha-2 territory validation
import pycountry


class IntakeValidator:
    REQUIRED_FIELDS = {
        "metadata": [
            "batch_id",
            "source_system",
            "source_file",
            "uploaded_at",
            "uploaded_by",
            "schema_version",
        ],
        "production": [
            "production_id",
            "title",
            "production_type",
            "release_date",
            "requested_territories",
            "distribution_scope",
            "status",
        ],
        "assets": [
            "asset_id",
            "title",
            "asset_type",
            "rights_holder",
            "description",
        ],
        "licenses": [
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
        ],
        "asset_usage": [
            "usage_id",
            "production_id",
            "asset_id",
            "scene_number",
            "usage_type",
            "duration_seconds",
            "prominence",
            "notes",
        ],
    }

    # Case-insensitive patterns for detecting possible prompt injection.
    # These patterns do not prove malicious intent. They trigger human review.
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(?:previous|all)\s+instructions",
        r"system\s+prompt",
        r"mark\s+this\s+asset\s+cleared",
        r"override",
        r"do\s+not\s+follow",
    ]

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.raw_bytes = b""
        self.raw_payload = {}
        self.normalized_payload = {}
        self.valid_sections = set()
        self.issues = []
        self.status = "READY"
        self.checksum = ""

    def _add_issue(
        self,
        issue_type: str,
        severity: str,
        record_type: str,
        record_id: Any,
        field: str,
        message: str,
        repairable: bool = False,
    ):
        """Append a structured validation issue to the report."""
        self.issues.append(
            {
                "issue_type": issue_type,
                "severity": severity,
                "record_type": record_type,
                "record_id": record_id,
                "field": field,
                "message": message,
                "repairable": repairable,
            }
        )

    def validate(self) -> Dict[str, Any]:
        """Execute the full deterministic validation pipeline."""
        self._load_and_hash()

        # If the file could not be loaded or parsed as valid JSON, halt early.
        if self.status == "QUARANTINED":
            return self._build_report()

        # 1. Root Type Check
        #
        # RightsReady expects every incoming package to have a JSON object
        # at its root. Valid JSON such as [], "hello", 123, true, or null
        # must therefore be rejected safely before we try dictionary methods.
        if not isinstance(self.raw_payload, dict):
            self._add_issue(
                "INVALID_STRUCTURE",
                "ERROR",
                "root",
                "root",
                "root",
                "Root payload has invalid type. Expected a JSON object (dict).",
            )

            self.normalized_payload = {}
            self.status = "QUARANTINED"
            return self._build_report()

        # Remove test-only expectations before business validation.
        # They must never become part of normalized business data.
        self.raw_payload.pop("_test_expectations", None)

        # Create a separate business-ready copy.
        # The source file and original parsed payload are not modified by
        # normalization work performed later.
        self.normalized_payload = copy.deepcopy(self.raw_payload)

        # 2. Verify top-level section structure and collection element types.
        self._check_sections_and_types()

        # 3. Check required fields only on structurally valid sections.
        self._check_required_fields()

        # 4. Normalize safe formatting issues.
        self._normalize_payload()

        # Remaining validation operates on normalized business data.
        #
        # This means IDs such as "ast-105   " become "AST-105" before
        # referential-integrity comparisons are performed.
        self._check_duplicates()
        self._validate_dates()
        self._validate_territories()
        self._validate_references()
        self._check_prompt_injection()

        self._determine_status()
        return self._build_report()

    def _load_and_hash(self):
        """
        Read the original file bytes, calculate SHA-256, and parse JSON.

        The checksum is calculated BEFORE normalization or test metadata
        removal. This allows RightsReady to identify exactly which uploaded
        file produced a particular validation result.
        """
        try:
            with open(self.file_path, "rb") as file:
                self.raw_bytes = file.read()

            self.checksum = hashlib.sha256(self.raw_bytes).hexdigest()

            self.raw_payload = json.loads(
                self.raw_bytes.decode("utf-8")
            )

        except (IOError, json.JSONDecodeError) as error:
            self._add_issue(
                "PARSE_ERROR",
                "ERROR",
                "file",
                None,
                "file",
                str(error),
            )
            self.status = "QUARANTINED"

    def _check_sections_and_types(self):
        """
        Verify all required top-level sections exist and use the expected
        JSON structure.

        It also verifies that collection elements are JSON objects.

        When a top-level section has an invalid type, RightsReady replaces
        that section in the normalized copy with a safe empty structure.
        This lets the rest of the validator continue without crashing while
        still quarantining the package.
        """

        expected_types = {
            "metadata": dict,
            "production": dict,
            "assets": list,
            "licenses": list,
            "asset_usage": list,
        }

        for section, expected_type in expected_types.items():

            # Required section is completely missing.
            if section not in self.normalized_payload:
                self._add_issue(
                    "MISSING_REQUIRED_FIELD",
                    "ERROR",
                    "root",
                    "root",
                    section,
                    f"Missing required top-level section: {section}",
                )

                # Inject a safe default for downstream validation.
                self.normalized_payload[section] = expected_type()

            # Section exists but has the wrong JSON type.
            elif not isinstance(
                self.normalized_payload[section],
                expected_type,
            ):
                self._add_issue(
                    "INVALID_STRUCTURE",
                    "ERROR",
                    "root",
                    "root",
                    section,
                    (
                        f"Section '{section}' has invalid type. "
                        f"Expected {expected_type.__name__}."
                    ),
                )

                # Replace malformed section in normalized output so later
                # functions do not raise AttributeError or TypeError.
                self.normalized_payload[section] = expected_type()

            else:
                self.valid_sections.add(section)

                # assets, licenses, and asset_usage are arrays.
                # Every individual record inside them must be an object.
                if expected_type is list:
                    collection = self.normalized_payload[section]

                    for index, record in enumerate(collection):
                        if not isinstance(record, dict):
                            self._add_issue(
                                "INVALID_STRUCTURE",
                                "ERROR",
                                section,
                                f"index_{index}",
                                "record",
                                (
                                    f"Element at index {index} in "
                                    f"'{section}' has invalid type. "
                                    "Expected dict/object."
                                ),
                            )

    def _check_required_fields(self):
        """
        Verify required fields within each structurally valid section.
        """

        # Metadata
        if "metadata" in self.valid_sections:
            metadata = self.normalized_payload.get(
                "metadata",
                {},
            )

            for field in self.REQUIRED_FIELDS["metadata"]:
                if (
                    field not in metadata
                    or metadata[field] is None
                    or metadata[field] == ""
                ):
                    self._add_issue(
                        "MISSING_REQUIRED_FIELD",
                        "ERROR",
                        "metadata",
                        None,
                        field,
                        f"Missing required metadata field: {field}",
                    )

        # Production
        if "production" in self.valid_sections:
            production = self.normalized_payload.get(
                "production",
                {},
            )

            production_id = production.get("production_id")

            for field in self.REQUIRED_FIELDS["production"]:
                if (
                    field not in production
                    or production[field] is None
                    or production[field] == ""
                ):
                    self._add_issue(
                        "MISSING_REQUIRED_FIELD",
                        "ERROR",
                        "production",
                        production_id,
                        field,
                        f"Missing required production field: {field}",
                    )

        # Collection records
        if "assets" in self.valid_sections:
            self._check_collection_fields(
                "assets",
                "asset_id",
            )

        if "licenses" in self.valid_sections:
            self._check_collection_fields(
                "licenses",
                "license_id",
            )

        if "asset_usage" in self.valid_sections:
            self._check_collection_fields(
                "asset_usage",
                "usage_id",
            )

    def _check_collection_fields(
        self,
        collection_name: str,
        id_field: str,
    ):
        """
        Validate required fields for each object inside a collection.

        Malformed non-object elements were already reported as
        INVALID_STRUCTURE, so they are skipped safely here.
        """

        collection = self.normalized_payload.get(
            collection_name,
            [],
        )

        for index, record in enumerate(collection):

            if not isinstance(record, dict):
                continue

            record_id = record.get(id_field)

            for field in self.REQUIRED_FIELDS[collection_name]:
                if (
                    field not in record
                    or record[field] is None
                    or record[field] == ""
                ):
                    self._add_issue(
                        "MISSING_REQUIRED_FIELD",
                        "ERROR",
                        collection_name,
                        record_id,
                        field,
                        (
                            f"Missing required field '{field}' "
                            f"in {collection_name} record "
                            f"(index {index})"
                        ),
                    )

    def _normalize_payload(self):
        """
        Normalize safe string-formatting problems while reporting them.

        Normalization itself is a WARNING and does not automatically
        quarantine a package.
        """

        def _clean_and_check(
            record: Dict,
            key: str,
            record_type: str,
            record_id: Any,
            is_id: bool,
        ):
            if not isinstance(record, dict):
                return

            value = record.get(key)

            if not isinstance(value, str):
                return

            if is_id:
                # IDs use trimmed uppercase canonical representation.
                new_value = value.strip().upper()

            else:
                # Human-readable text has repeated whitespace collapsed.
                new_value = re.sub(
                    r"\s+",
                    " ",
                    value,
                ).strip()

            if new_value != value:
                self._add_issue(
                    "NORMALIZATION_REQUIRED",
                    "WARNING",
                    record_type,
                    record_id,
                    key,
                    "Whitespace or casing required normalization.",
                    repairable=True,
                )

                record[key] = new_value

        # Production
        production = self.normalized_payload.get(
            "production",
            {},
        )

        if isinstance(production, dict):
            production_id = production.get(
                "production_id"
            )

            _clean_and_check(
                production,
                "production_id",
                "production",
                production_id,
                is_id=True,
            )

            _clean_and_check(
                production,
                "title",
                "production",
                production_id,
                is_id=False,
            )

            if (
                "requested_territories" in production
                and isinstance(
                    production["requested_territories"],
                    list,
                )
            ):
                normalized_territories = []

                for territory in production[
                    "requested_territories"
                ]:
                    new_territory = (
                        territory.strip().upper()
                        if isinstance(territory, str)
                        else territory
                    )

                    if new_territory != territory:
                        self._add_issue(
                            "NORMALIZATION_REQUIRED",
                            "WARNING",
                            "production",
                            production_id,
                            "requested_territories",
                            "Territory normalized.",
                            repairable=True,
                        )

                    normalized_territories.append(
                        new_territory
                    )

                production[
                    "requested_territories"
                ] = normalized_territories

        # Assets
        for asset in self.normalized_payload.get(
            "assets",
            [],
        ):
            if isinstance(asset, dict):
                asset_id = asset.get("asset_id")

                _clean_and_check(
                    asset,
                    "asset_id",
                    "assets",
                    asset_id,
                    is_id=True,
                )

                _clean_and_check(
                    asset,
                    "title",
                    "assets",
                    asset_id,
                    is_id=False,
                )

                _clean_and_check(
                    asset,
                    "description",
                    "assets",
                    asset_id,
                    is_id=False,
                )

        # Licenses
        for license_record in self.normalized_payload.get(
            "licenses",
            [],
        ):
            if isinstance(license_record, dict):
                license_id = license_record.get(
                    "license_id"
                )

                _clean_and_check(
                    license_record,
                    "license_id",
                    "licenses",
                    license_id,
                    is_id=True,
                )

                _clean_and_check(
                    license_record,
                    "asset_id",
                    "licenses",
                    license_id,
                    is_id=True,
                )

                if (
                    "permitted_territories"
                    in license_record
                    and isinstance(
                        license_record[
                            "permitted_territories"
                        ],
                        list,
                    )
                ):
                    normalized_territories = []

                    for territory in license_record[
                        "permitted_territories"
                    ]:
                        new_territory = (
                            territory.strip().upper()
                            if isinstance(
                                territory,
                                str,
                            )
                            else territory
                        )

                        if new_territory != territory:
                            self._add_issue(
                                "NORMALIZATION_REQUIRED",
                                "WARNING",
                                "licenses",
                                license_id,
                                "permitted_territories",
                                "Territory normalized.",
                                repairable=True,
                            )

                        normalized_territories.append(
                            new_territory
                        )

                    license_record[
                        "permitted_territories"
                    ] = normalized_territories

        # Asset usage
        for usage in self.normalized_payload.get(
            "asset_usage",
            [],
        ):
            if isinstance(usage, dict):
                usage_id = usage.get("usage_id")

                _clean_and_check(
                    usage,
                    "usage_id",
                    "asset_usage",
                    usage_id,
                    is_id=True,
                )

                _clean_and_check(
                    usage,
                    "production_id",
                    "asset_usage",
                    usage_id,
                    is_id=True,
                )

                _clean_and_check(
                    usage,
                    "asset_id",
                    "asset_usage",
                    usage_id,
                    is_id=True,
                )

                _clean_and_check(
                    usage,
                    "notes",
                    "asset_usage",
                    usage_id,
                    is_id=False,
                )

    def _check_duplicates(self):
        """Identify duplicate primary IDs inside collections."""

        seen_assets = set()

        for asset in self.normalized_payload.get(
            "assets",
            [],
        ):
            if not isinstance(asset, dict):
                continue

            asset_id = asset.get("asset_id")

            if asset_id:
                if asset_id in seen_assets:
                    self._add_issue(
                        "DUPLICATE_ID",
                        "ERROR",
                        "assets",
                        asset_id,
                        "asset_id",
                        f"Duplicate asset_id: {asset_id}",
                    )

                seen_assets.add(asset_id)

        seen_licenses = set()

        for license_record in self.normalized_payload.get(
            "licenses",
            [],
        ):
            if not isinstance(license_record, dict):
                continue

            license_id = license_record.get(
                "license_id"
            )

            if license_id:
                if license_id in seen_licenses:
                    self._add_issue(
                        "DUPLICATE_ID",
                        "ERROR",
                        "licenses",
                        license_id,
                        "license_id",
                        (
                            "Duplicate license_id: "
                            f"{license_id}"
                        ),
                    )

                seen_licenses.add(license_id)

        seen_usages = set()

        for usage in self.normalized_payload.get(
            "asset_usage",
            [],
        ):
            if not isinstance(usage, dict):
                continue

            usage_id = usage.get("usage_id")

            if usage_id:
                if usage_id in seen_usages:
                    self._add_issue(
                        "DUPLICATE_ID",
                        "ERROR",
                        "asset_usage",
                        usage_id,
                        "usage_id",
                        f"Duplicate usage_id: {usage_id}",
                    )

                seen_usages.add(usage_id)

    def _validate_dates(self):
        """
        Validate YYYY-MM-DD date strings and license date ordering.
        """

        def _parse_date(
            date_string,
            record_type,
            record_id,
            field,
        ):
            if (
                not date_string
                or not isinstance(date_string, str)
            ):
                return None

            try:
                return datetime.strptime(
                    date_string,
                    "%Y-%m-%d",
                )

            except ValueError:
                self._add_issue(
                    "INVALID_DATE",
                    "ERROR",
                    record_type,
                    record_id,
                    field,
                    (
                        "Invalid date format or value: "
                        f"{date_string}"
                    ),
                )

                return None

        # Production release date
        production = self.normalized_payload.get(
            "production",
            {},
        )

        if isinstance(production, dict):
            _parse_date(
                production.get("release_date"),
                "production",
                production.get("production_id"),
                "release_date",
            )

        # License dates
        for license_record in self.normalized_payload.get(
            "licenses",
            [],
        ):
            if not isinstance(license_record, dict):
                continue

            license_id = license_record.get(
                "license_id"
            )

            valid_from = _parse_date(
                license_record.get("valid_from"),
                "licenses",
                license_id,
                "valid_from",
            )

            valid_until = _parse_date(
                license_record.get("valid_until"),
                "licenses",
                license_id,
                "valid_until",
            )

            if (
                valid_from
                and valid_until
                and valid_from > valid_until
            ):
                self._add_issue(
                    "INVALID_DATE_RANGE",
                    "ERROR",
                    "licenses",
                    license_id,
                    "valid_from/valid_until",
                    (
                        f"valid_from "
                        f"({license_record.get('valid_from')}) "
                        "is later than valid_until "
                        f"({license_record.get('valid_until')})"
                    ),
                )

    def _validate_territories(self):
        """
        Validate territory arrays.

        Allowed values:
        - ISO 3166-1 alpha-2 country codes
        - WORLDWIDE
        """

        def _check_territory_list(
            territory_list,
            record_type,
            record_id,
            field,
        ):
            if not isinstance(territory_list, list):
                return

            for code in territory_list:

                if code == "WORLDWIDE":
                    continue

                if (
                    not isinstance(code, str)
                    or not pycountry.countries.get(
                        alpha_2=code
                    )
                ):
                    self._add_issue(
                        "INVALID_TERRITORY",
                        "ERROR",
                        record_type,
                        record_id,
                        field,
                        f"Invalid territory code: {code}",
                    )

        production = self.normalized_payload.get(
            "production",
            {},
        )

        if isinstance(production, dict):
            _check_territory_list(
                production.get(
                    "requested_territories",
                    [],
                ),
                "production",
                production.get("production_id"),
                "requested_territories",
            )

        for license_record in self.normalized_payload.get(
            "licenses",
            [],
        ):
            if isinstance(license_record, dict):
                _check_territory_list(
                    license_record.get(
                        "permitted_territories",
                        [],
                    ),
                    "licenses",
                    license_record.get(
                        "license_id"
                    ),
                    "permitted_territories",
                )

    def _validate_references(self):
        """
        Verify referential integrity between assets, licenses, usages,
        and the package production.
        """

        valid_assets = set()

        for asset in self.normalized_payload.get(
            "assets",
            [],
        ):
            if (
                isinstance(asset, dict)
                and asset.get("asset_id")
            ):
                valid_assets.add(
                    asset.get("asset_id")
                )

        production = self.normalized_payload.get(
            "production",
            {},
        )

        package_production_id = (
            production.get("production_id")
            if isinstance(production, dict)
            else None
        )

        # Every license must reference an existing asset.
        for license_record in self.normalized_payload.get(
            "licenses",
            [],
        ):
            if not isinstance(license_record, dict):
                continue

            asset_id = license_record.get("asset_id")

            if (
                asset_id
                and asset_id not in valid_assets
            ):
                self._add_issue(
                    "BROKEN_REFERENCE",
                    "ERROR",
                    "licenses",
                    license_record.get(
                        "license_id"
                    ),
                    "asset_id",
                    (
                        "License references missing "
                        f"asset_id: {asset_id}"
                    ),
                )

        # Usage records must reference existing assets and the package
        # production.
        for usage in self.normalized_payload.get(
            "asset_usage",
            [],
        ):
            if not isinstance(usage, dict):
                continue

            usage_id = usage.get("usage_id")
            asset_id = usage.get("asset_id")
            production_id = usage.get(
                "production_id"
            )

            if (
                asset_id
                and asset_id not in valid_assets
            ):
                self._add_issue(
                    "BROKEN_REFERENCE",
                    "ERROR",
                    "asset_usage",
                    usage_id,
                    "asset_id",
                    (
                        "Usage references missing "
                        f"asset_id: {asset_id}"
                    ),
                )

            if (
                production_id
                and package_production_id
                and production_id
                != package_production_id
            ):
                self._add_issue(
                    "BROKEN_REFERENCE",
                    "ERROR",
                    "asset_usage",
                    usage_id,
                    "production_id",
                    (
                        "Usage production_id "
                        f"({production_id}) does not match "
                        "package production_id "
                        f"({package_production_id})"
                    ),
                )

    def _check_prompt_injection(self):
        """
        Scan untrusted free-text fields for possible prompt-injection
        patterns.

        Detection does NOT imply malicious intent. It creates a
        SECURITY_REVIEW issue so a human can inspect the text before
        it reaches downstream AI reasoning.
        """

        compiled_patterns = [
            re.compile(
                pattern,
                re.IGNORECASE,
            )
            for pattern
            in self.PROMPT_INJECTION_PATTERNS
        ]

        def _scan_text(
            text: str,
            record_type: str,
            record_id: Any,
            field: str,
        ):
            if (
                not text
                or not isinstance(text, str)
            ):
                return

            for pattern in compiled_patterns:
                if pattern.search(text):
                    self._add_issue(
                        "POSSIBLE_PROMPT_INJECTION",
                        "SECURITY_REVIEW",
                        record_type,
                        record_id,
                        field,
                        (
                            "Suspicious instruction pattern "
                            f"detected in field '{field}'."
                        ),
                    )

                    # One flag per field is sufficient even if several
                    # suspicious patterns match.
                    break

        # Asset descriptions
        for asset in self.normalized_payload.get(
            "assets",
            [],
        ):
            if isinstance(asset, dict):
                _scan_text(
                    asset.get("description"),
                    "assets",
                    asset.get("asset_id"),
                    "description",
                )

        # Asset-usage notes
        for usage in self.normalized_payload.get(
            "asset_usage",
            [],
        ):
            if isinstance(usage, dict):
                _scan_text(
                    usage.get("notes"),
                    "asset_usage",
                    usage.get("usage_id"),
                    "notes",
                )

    def _determine_status(self):
        """
        READY:
            No ERROR or SECURITY_REVIEW issues.

        QUARANTINED:
            At least one ERROR or SECURITY_REVIEW issue.

        WARNING-only packages remain READY.
        """

        for issue in self.issues:
            if issue["severity"] in [
                "ERROR",
                "SECURITY_REVIEW",
            ]:
                self.status = "QUARANTINED"
                return

        self.status = "READY"

    def _build_report(self) -> Dict[str, Any]:
        """Construct the final structured validation report."""

        return {
            "status": self.status,
            "checksum_sha256": self.checksum,
            "issue_count": len(self.issues),
            "issues": self.issues,
            "normalized_payload": self.normalized_payload,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RightsReady Intake Validator"
    )

    parser.add_argument(
        "file",
        help="Path to the JSON rights package",
    )

    args = parser.parse_args()

    validator = IntakeValidator(args.file)
    report = validator.validate()

    # Print a human-readable JSON validation report.
    print(
        json.dumps(
            report,
            indent=2,
        )
    )

    # READY returns shell exit code 0.
    # QUARANTINED returns exit code 1 so automation can detect failure.
    if report["status"] == "QUARANTINED":
        sys.exit(1)

    sys.exit(0)