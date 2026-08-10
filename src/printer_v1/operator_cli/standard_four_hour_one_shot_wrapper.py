"""Standard-four-hour one-shot authorization and wrapper contract.

The pure document helpers in this module are intentionally usable by offline
fixture proof. A real one-shot child launcher is added only after the separate
manifest/application-marker integration is proven.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


WRAPPER_SCHEMA_VERSION = "PRINTER_V1_STANDARD_FOUR_HOUR_ONE_SHOT_WRAPPER_V1"
FINAL_AUTHORIZATION_SCHEMA_VERSION = "PRINTER_V1_STANDARD_FOUR_HOUR_FINAL_AUTHORIZATION_V1"
AUTHORIZED_COMMAND_MODE = "standard-four-hour-run"
ELIGIBILITY_CONTRACT_VERSION = "STANDARD_4H_ELIGIBILITY_V1"
POLICY_VERSION = "V2-9.8-STANDARD-4H-OPERATIONAL-V1"
POST_SUPPLY_DURATION_SECONDS = 14_700
PRE_LIFECYCLE_DURATION_SECONDS = 900
LIFECYCLE_REQUEST_OUTER_CEILING = 230
LIFECYCLE_SCHEDULER_OUTER_CEILING = 210
LOCKED_WINDOWS = ("WINDOW_12H", "WINDOW_24H")
_HEAD = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class StandardFourHourOneShotWrapperError(RuntimeError):
    """Fail-closed standard-four-hour wrapper/authorization contract error."""


def fixture_authorization_document(
    *, branch: str, head: str, database: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": FINAL_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_id": "FIXTURE_STANDARD_FOUR_HOUR_AUTHORIZATION",
        "repository": {"branch": str(branch), "head": str(head)},
        "authorized_command": {
            "mode": AUTHORIZED_COMMAND_MODE,
            "operator_approved": True,
        },
        "one_shot_policy": {
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        },
        "campaign_policy": {
            "policy_version": POLICY_VERSION,
            "token_capacity": 2,
            "root_main_window": "WINDOW_15M",
            "post_supply_duration_seconds": POST_SUPPLY_DURATION_SECONDS,
            "pre_lifecycle_duration_seconds": PRE_LIFECYCLE_DURATION_SECONDS,
            "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
            "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
            "eligibility_contract_version": ELIGIBILITY_CONTRACT_VERSION,
            "locked_windows": list(LOCKED_WINDOWS),
        },
        "authoritative_database": dict(database),
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StandardFourHourOneShotWrapperError(message)


def validate_standard_four_hour_authorization_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    _require(isinstance(document, Mapping), "authorization must be an object")
    required = {
        "schema_version", "authorization_id", "repository", "authorized_command",
        "one_shot_policy", "campaign_policy", "authoritative_database",
    }
    _require(set(document) == required, "authorization schema keys are malformed")
    _require(
        document.get("schema_version") == FINAL_AUTHORIZATION_SCHEMA_VERSION,
        "authorization schema version mismatch",
    )
    repository = document.get("repository")
    _require(isinstance(repository, Mapping), "repository binding is malformed")
    _require(set(repository) == {"branch", "head"}, "repository keys are malformed")
    _require(type(repository.get("branch")) is str and bool(repository.get("branch")), "branch is malformed")
    _require(type(repository.get("head")) is str and _HEAD.fullmatch(str(repository.get("head"))) is not None, "head is malformed")

    command = document.get("authorized_command")
    _require(isinstance(command, Mapping), "authorized command is malformed")
    _require(set(command) == {"mode", "operator_approved"}, "authorized command keys are malformed")
    _require(command.get("mode") == AUTHORIZED_COMMAND_MODE, "authorized command mode mismatch")
    _require(command.get("operator_approved") is True, "operator approval must be true")

    one_shot = document.get("one_shot_policy")
    _require(isinstance(one_shot, Mapping), "one-shot policy is malformed")
    _require(one_shot.get("allowed_invocation_count") == 1, "allowed invocation count must be one")
    for key in (
        "automatic_retry_allowed", "manual_rerun_allowed", "resume_allowed",
        "restart_allowed", "successor_allowed",
    ):
        _require(one_shot.get(key) is False, f"{key} must be false")

    campaign = document.get("campaign_policy")
    _require(isinstance(campaign, Mapping), "campaign policy is malformed")
    expected_campaign = {
        "policy_version": POLICY_VERSION,
        "token_capacity": 2,
        "root_main_window": "WINDOW_15M",
        "post_supply_duration_seconds": POST_SUPPLY_DURATION_SECONDS,
        "pre_lifecycle_duration_seconds": PRE_LIFECYCLE_DURATION_SECONDS,
        "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
        "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
        "eligibility_contract_version": ELIGIBILITY_CONTRACT_VERSION,
        "locked_windows": list(LOCKED_WINDOWS),
    }
    _require(dict(campaign) == expected_campaign, "campaign policy mismatch")

    database = document.get("authoritative_database")
    _require(isinstance(database, Mapping), "authoritative database binding is malformed")
    required_db = {
        "path", "sha256", "size", "inode", "mtime_ns", "migration_count", "migration_head",
    }
    _require(set(database) == required_db, "authoritative database keys are malformed")
    _require(type(database.get("path")) is str and bool(database.get("path")), "database path is malformed")
    _require(type(database.get("sha256")) is str and _SHA256.fullmatch(str(database.get("sha256"))) is not None, "database sha256 is malformed")
    for key in ("size", "inode", "mtime_ns", "migration_count"):
        _require(type(database.get(key)) is int and int(database.get(key)) >= 0, f"database {key} is malformed")
    _require(type(database.get("migration_head")) is str and bool(database.get("migration_head")), "migration head is malformed")
    return copy.deepcopy(dict(document))
