from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected patch anchor missing in {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def create(path: str, content: str) -> None:
    target = Path(path)
    if target.exists():
        raise RuntimeError(f"refusing to overwrite new file: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public operational policy identity.  This slice exposes the explicit mode
# contract but intentionally keeps the runnable standard mode blocked until the
# later factory/wrapper integration slice is installed and proved.
# ---------------------------------------------------------------------------
replace_once(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py",
    'SELECTIVE_1H_CONTINUATION_SECONDS = 2_700\n',
    '''SELECTIVE_1H_CONTINUATION_SECONDS = 2_700
STANDARD_FOUR_HOUR_MODE = "standard-four-hour-run"
STANDARD_FOUR_HOUR_PREFLIGHT_MODE = "standard-four-hour-preflight"
STANDARD_FOUR_HOUR_POLICY_VERSION = "V2-9.8-STANDARD-4H-OPERATIONAL-V1"
STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS = 14_700
STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING = 230
STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN = 114
STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING = 210
''',
)
replace_once(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py",
    '''    pre_lifecycle_acquisition_duration_seconds: int = (
        PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
    )
''',
    '''    pre_lifecycle_acquisition_duration_seconds: int = (
        PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
    )
    continuous_four_hour: bool = False
    standard_four_hour_campaign: bool = False
''',
)
replace_once(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py",
    '''_SELECTIVE_1H_PROOF_POLICY = _OperationalCampaignPolicy(
    mode=SELECTIVE_1H_MODE,
    duration_seconds=SELECTIVE_1H_TOTAL_DURATION_SECONDS,
    selective_1h_continuation=True,
    governed_request_ceiling=SELECTIVE_1H_GOVERNED_REQUEST_CEILING,
    governed_requests_per_token=SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=SELECTIVE_1H_SCHEDULER_ROW_CEILING,
    locked_windows=("WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
)
''',
    '''_SELECTIVE_1H_PROOF_POLICY = _OperationalCampaignPolicy(
    mode=SELECTIVE_1H_MODE,
    duration_seconds=SELECTIVE_1H_TOTAL_DURATION_SECONDS,
    selective_1h_continuation=True,
    governed_request_ceiling=SELECTIVE_1H_GOVERNED_REQUEST_CEILING,
    governed_requests_per_token=SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=SELECTIVE_1H_SCHEDULER_ROW_CEILING,
    locked_windows=("WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
)
STANDARD_FOUR_HOUR_POLICY = _OperationalCampaignPolicy(
    mode=STANDARD_FOUR_HOUR_MODE,
    duration_seconds=STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS,
    selective_1h_continuation=True,
    governed_request_ceiling=STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING,
    governed_requests_per_token=STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING,
    locked_windows=("WINDOW_12H", "WINDOW_24H"),
    pre_lifecycle_acquisition_duration_seconds=(
        PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
    ),
    continuous_four_hour=True,
    standard_four_hour_campaign=True,
)
''',
)
replace_once(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py",
    '''            "Printer V1 bounded persistent 15m Memory Factory command. "
            "Modes: preflight-only, run, selective-1h-preflight, "
            "selective-1h-proof, status, cooperative-stop, recover-orphan, "
''',
    '''            "Printer V1 bounded persistent Memory Factory command. "
            "Modes: preflight-only, run, selective-1h-preflight, "
            "selective-1h-proof, standard-four-hour-preflight, "
            "standard-four-hour-run, status, cooperative-stop, recover-orphan, "
''',
)
replace_once(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py",
    '''            "preflight-only", "run", SELECTIVE_1H_PREFLIGHT_MODE,
            SELECTIVE_1H_MODE, "status", "cooperative-stop", "recover-orphan",
''',
    '''            "preflight-only", "run", SELECTIVE_1H_PREFLIGHT_MODE,
            SELECTIVE_1H_MODE, STANDARD_FOUR_HOUR_PREFLIGHT_MODE,
            STANDARD_FOUR_HOUR_MODE, "status", "cooperative-stop", "recover-orphan",
''',
)
# Fail closed while slice B/C authority integration is not yet present.
replace_once(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py",
    '''        if args.mode == "preflight-only":
            result = build_activation_preflight(
''',
    '''        if args.mode == STANDARD_FOUR_HOUR_MODE:
            raise OperationalMemoryFactoryError(
                "standard four-hour run is not active until one-shot/factory authority integration passes"
            )
        if args.mode == STANDARD_FOUR_HOUR_PREFLIGHT_MODE:
            result = build_activation_preflight(
                git_provenance_authorization=git_provenance_authorization
            )
        elif args.mode == "preflight-only":
            result = build_activation_preflight(
''',
)

# ---------------------------------------------------------------------------
# Explicit proof-vs-standard 4h execution authority. Existing proof callers keep
# working through explicit_proof_mode compatibility; standard campaign planning
# remains owned by the campaign-level composer.
# ---------------------------------------------------------------------------
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    'import sqlite3\nfrom typing import Any, Mapping, Sequence\n',
    'import sqlite3\nfrom enum import StrEnum\nfrom typing import Any, Mapping, Sequence\n',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''CONTEXT_PLAN = {
    "opening": ("market_chain", "entry_quote"),
    "closing": ("market_chain", "safety", "exit_quote"),
    "holder_fallback_max": 2,  # V2-9.6: 1 primary holder fallback + 1 backup RPC endpoint
}
''',
    '''CONTEXT_PLAN = {
    "opening": ("market_chain", "entry_quote"),
    "closing": ("market_chain", "safety", "exit_quote"),
    "holder_fallback_max": 2,  # V2-9.6: 1 primary holder fallback + 1 backup RPC endpoint
}


class FourHourExecutionAuthority(StrEnum):
    DISABLED = "DISABLED"
    PROOF = "PROOF"
    STANDARD_CAMPAIGN = "STANDARD_CAMPAIGN"
''',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''    current_close_step_id: int | None = None,
    explicit_proof_mode: bool = False,
    compressed_two_token_proof: bool = False,
''',
    '''    current_close_step_id: int | None = None,
    execution_authority: FourHourExecutionAuthority | str = FourHourExecutionAuthority.DISABLED,
    explicit_proof_mode: bool = False,
    compressed_two_token_proof: bool = False,
''',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''    """Plan the exact policy-derived 4h jobs from this run's terminal 1h row."""
    if not explicit_proof_mode:
        return {
            "planned": False,
            "blocked_reasons": ["WINDOW_4H real collection remains disabled"],
        }
''',
    '''    """Plan the exact policy-derived 4h jobs from this run's terminal 1h row."""
    try:
        authority = FourHourExecutionAuthority(execution_authority)
    except ValueError:
        return {"planned": False, "blocked_reasons": ["invalid_4h_execution_authority"]}
    if explicit_proof_mode:
        if authority not in {FourHourExecutionAuthority.DISABLED, FourHourExecutionAuthority.PROOF}:
            return {"planned": False, "blocked_reasons": ["conflicting_4h_execution_authority"]}
        authority = FourHourExecutionAuthority.PROOF
    if authority == FourHourExecutionAuthority.STANDARD_CAMPAIGN:
        return {
            "planned": False,
            "blocked_reasons": ["standard_campaign_4h_planning_requires_campaign_composer"],
        }
    if authority != FourHourExecutionAuthority.PROOF:
        return {
            "planned": False,
            "blocked_reasons": ["WINDOW_4H execution authority is disabled"],
        }
''',
)
# Planning is an offline/campaign composition primitive; cadence activation is
# no longer itself a reason to reject the already-authorized composer.
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''    if bool(budget["real_collection_enabled"]):
        raise ValueError("eligible-subset repair must not enable real WINDOW_4H collection")

''',
    '',
)

# ---------------------------------------------------------------------------
# Activate only the existing, already-proven 4h cadence. 12h/24h remain false.
# ---------------------------------------------------------------------------
replace_once(
    "src/printer_v1/snapshots/cadence_policy.py",
    '''  - WINDOW_4H / WINDOW_12H / WINDOW_24H have fixture-testable cadence
    contracts but remain disabled for real collection.
''',
    '''  - WINDOW_4H is enabled only through the explicit standard-four-hour
    operational authority; WINDOW_12H / WINDOW_24H remain disabled.
''',
)
replace_once(
    "src/printer_v1/snapshots/cadence_policy.py",
    '    # 4h / 12h / 24h — recognized but disabled for real collection.\n',
    '    # 4h is explicitly operationally activated; 12h / 24h remain disabled.\n',
)
# Exact two 4h entries only.
text_path = Path("src/printer_v1/snapshots/cadence_policy.py")
text = text_path.read_text(encoding="utf-8")
needle = 'window_kind="WINDOW_4H"'
start = 0
changed = 0
while True:
    pos = text.find(needle, start)
    if pos < 0:
        break
    next_entry = text.find("SnapshotCadencePolicy(", pos + len(needle))
    end = next_entry if next_entry >= 0 else len(text)
    segment = text[pos:end]
    old = "enabled_for_real_collection=False"
    if old not in segment:
        raise RuntimeError("WINDOW_4H cadence entry missing disabled flag")
    segment = segment.replace(old, "enabled_for_real_collection=True", 1)
    text = text[:pos] + segment + text[end:]
    changed += 1
    start = pos + len(segment)
if changed != 2:
    raise RuntimeError(f"expected exactly two WINDOW_4H cadence entries, changed {changed}")
text_path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Pure campaign-level hard-gate adapter. It performs no IO or persistence.
# ---------------------------------------------------------------------------
create(
    "src/printer_v1/operator_cli/operational_standard_4h.py",
    '''"""Pure production standard-four-hour campaign eligibility boundary.

No source fetch, Scheduler mutation, database mutation, or successor creation is
performed here. The canonical token-local continuation policy remains the sole
hard-gate evaluator; this module only enforces the post-DTW100 1h->4h verdict
vocabulary and returns the exact eligible slot subset.
"""

from __future__ import annotations

from typing import Iterable

from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationVerdict,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)


STANDARD_FOUR_HOUR_ALLOWED_VERDICTS = frozenset(
    {
        ContinuationVerdict.CONTINUE_TO_WINDOW_4H.value,
        ContinuationVerdict.BLOCK_CONTINUATION.value,
    }
)


class StandardFourHourOperationalError(RuntimeError):
    """Fail-closed standard-four-hour campaign-barrier error."""


def evaluate_standard_four_hour_eligibility(
    *,
    campaign: CampaignContinuationContext,
    tokens: Iterable[TokenContinuationInput],
) -> dict[str, object]:
    token_inputs = tuple(tokens)
    if len(token_inputs) != 2:
        raise StandardFourHourOperationalError(
            "standard four-hour campaign barrier requires exactly two token slots"
        )
    try:
        results = evaluate_token_local_continuations(
            campaign=campaign,
            tokens=token_inputs,
        )
    except Exception as exc:
        raise StandardFourHourOperationalError(str(exc)) from exc

    verdicts: dict[str, str] = {}
    reasons: dict[str, tuple[str, ...]] = {}
    eligible: list[str] = []
    for result in results:
        verdict = str(result.verdict)
        if verdict not in STANDARD_FOUR_HOUR_ALLOWED_VERDICTS:
            raise StandardFourHourOperationalError(
                f"unexpected standard 1h->4h verdict: {verdict}"
            )
        slot_id = str(result.token_slot_id)
        verdicts[slot_id] = verdict
        reasons[slot_id] = tuple(result.reasons)
        if verdict == ContinuationVerdict.CONTINUE_TO_WINDOW_4H.value:
            eligible.append(slot_id)
    return {
        "eligible_token_slot_ids": tuple(eligible),
        "continuation_count": len(eligible),
        "verdicts": verdicts,
        "reasons": reasons,
    }
''',
)

# ---------------------------------------------------------------------------
# Distinct, pure final-authorization document contract for fixture/offline TDD.
# Actual one-use file consumption/child launch is installed in the later slice.
# ---------------------------------------------------------------------------
create(
    "src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py",
    '''"""Standard-four-hour one-shot authorization and wrapper contract.

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
''',
)

# ---------------------------------------------------------------------------
# Versioned Git authorization profile descriptor. Existing ordinary validation
# remains unchanged in this slice.
# ---------------------------------------------------------------------------
replace_once(
    "src/printer_v1/operator_cli/git_provenance_authorization_manifest.py",
    '''REQUIRED_MAIN_WINDOW = "WINDOW_15M"
REQUIRED_COMMAND_MODE = "run"
''',
    '''REQUIRED_MAIN_WINDOW = "WINDOW_15M"
REQUIRED_COMMAND_MODE = "run"


@dataclass(frozen=True)
class GitAuthorizationProfile:
    command_mode: str
    authorization_package_root: str
    authorization_package_kind: str
    manifest_schema_version: str


STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE = GitAuthorizationProfile(
    command_mode="standard-four-hour-run",
    authorization_package_root=(
        "operator-runs/v2-9-8b-standard-four-hour-final-authorization"
    ),
    authorization_package_kind="STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE",
    manifest_schema_version="PRINTER_V1_GIT_PROVENANCE_MANIFEST_STANDARD_4H_V1",
)
''',
)

# ---------------------------------------------------------------------------
# Versioned child-terminal mode map while leaving ordinary run implementation
# unchanged until the later terminal integration slice.
# ---------------------------------------------------------------------------
replace_once(
    "src/printer_v1/operator_cli/window_15m_child_terminal.py",
    '''CHILD_TERMINAL_SCHEMA_VERSION = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1"
CHILD_TERMINAL_ENV_VAR = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH"
''',
    '''CHILD_TERMINAL_SCHEMA_VERSION = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1"
STANDARD_FOUR_HOUR_CHILD_TERMINAL_SCHEMA_VERSION = (
    "PRINTER_V1_STANDARD_FOUR_HOUR_CHILD_TERMINAL_V1"
)
CHILD_TERMINAL_MODE_SCHEMAS = {
    "run": CHILD_TERMINAL_SCHEMA_VERSION,
    "standard-four-hour-run": STANDARD_FOUR_HOUR_CHILD_TERMINAL_SCHEMA_VERSION,
}
CHILD_TERMINAL_ENV_VAR = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH"
''',
)

# ---------------------------------------------------------------------------
# Tests whose previous implementation-lane lock is deliberately superseded by
# this explicit activation lane.  Budget numbers and downstream locks remain.
# ---------------------------------------------------------------------------
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py",
    '''    def test_standard_policy_does_not_activate_real_4h_collection(self) -> None:
        self.assertFalse(four_hour.runtime_budget("TRACK_FAST")["enabled_for_real_collection"])
        self.assertFalse(four_hour.runtime_budget("TRACK_NORMAL")["enabled_for_real_collection"])
''',
    '''    def test_standard_activation_enables_real_4h_collection_only(self) -> None:
        self.assertTrue(four_hour.runtime_budget("TRACK_FAST")["enabled_for_real_collection"])
        self.assertTrue(four_hour.runtime_budget("TRACK_NORMAL")["enabled_for_real_collection"])
        from printer_v1.snapshots.cadence_policy import get_policy
        for lane in ("TRACK_FAST", "TRACK_NORMAL"):
            self.assertFalse(get_policy("WINDOW_12H", lane).enabled_for_real_collection)
            self.assertFalse(get_policy("WINDOW_24H", lane).enabled_for_real_collection)
''',
)
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_eligible_subset.py",
    '''            self.assertFalse(bool(budget["real_collection_enabled"]))
            self.assertEqual(int(budget["continuation_count"]), sum(mask))
''',
    '''            self.assertEqual(
                bool(budget["real_collection_enabled"]),
                bool(sum(mask)),
            )
            self.assertEqual(int(budget["continuation_count"]), sum(mask))
''',
)
