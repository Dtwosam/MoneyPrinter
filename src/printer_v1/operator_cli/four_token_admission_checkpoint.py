"""Bounded operational four-token admission-checkpoint authority.

The checkpoint exercises the real 4/2/2 operational admission path while
Cycle 1 owns its ordinary WINDOW_15M cadence. It does not alter the canonical
multi-cycle admission policy or its through-4h reserve arithmetic. Instead the
factory stops immediately after Cycle 2 reaches its one durable admission
outcome, with a separate 15-minute outer checkpoint deadline.

No WINDOW_1H, WINDOW_4H, WINDOW_12H or WINDOW_24H continuation is authorized.
This module performs no I/O and owns no independent source/Scheduler capacity.
"""

from __future__ import annotations

from typing import Any

from printer_v1.operator_cli import four_token_operational_composition as _base

FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE = "four-token-admission-checkpoint-run"
POLICY_VERSION = "V2-9.8B-FOUR-TOKEN-ADMISSION-CHECKPOINT-V1"
TERMINAL_CAUSE = "FOUR_TOKEN_ADMISSION_CHECKPOINT_COMPLETE"
TIMEOUT_CAUSE = "FOUR_TOKEN_ADMISSION_CHECKPOINT_TIMEOUT"
CHECKPOINT_RUNTIME_SECONDS = 900

PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = (
    _base.PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
)
POST_SUPPLY_LIFECYCLE_DURATION_SECONDS = (
    _base.POST_SUPPLY_LIFECYCLE_DURATION_SECONDS
)
MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS = (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS + CHECKPOINT_RUNTIME_SECONDS
)
LIFECYCLE_REQUEST_OUTER_CEILING = _base.LIFECYCLE_REQUEST_OUTER_CEILING
LIFECYCLE_REQUESTS_PER_TOKEN = _base.LIFECYCLE_REQUESTS_PER_TOKEN
LIFECYCLE_SCHEDULER_OUTER_CEILING = _base.LIFECYCLE_SCHEDULER_OUTER_CEILING
LOCKED_WINDOWS = ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")


def exact_admission_checkpoint_policy() -> dict[str, Any]:
    """Return the one exact reduced authority accepted by the checkpoint wrapper."""
    return {
        "policy_version": POLICY_VERSION,
        "execution_scope": "TWO_CYCLE_FOUR_TOKEN_ADMISSION_CHECKPOINT",
        "configured_tokens": _base.CONFIGURED_THROUGH_4H_TOKENS,
        "configured_active_cycles": _base.CONFIGURED_ACTIVE_CYCLES,
        "total_cycle_admission_ceiling": _base.TOTAL_CYCLE_ADMISSION_CEILING,
        "tokens_per_cycle": _base.TOKENS_PER_CYCLE,
        "minimum_cycle_admission_spacing_seconds": (
            _base.MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS
        ),
        "pre_lifecycle_acquisition_duration_seconds": (
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
        ),
        "later_cycle_pre_admission_deadline_seconds_after_cycle_one": (
            _base.LATER_CYCLE_PRE_ADMISSION_DEADLINE_SECONDS_AFTER_CYCLE_ONE
        ),
        "controller_post_supply_horizon_seconds": (
            POST_SUPPLY_LIFECYCLE_DURATION_SECONDS
        ),
        "checkpoint_runtime_seconds": CHECKPOINT_RUNTIME_SECONDS,
        "cycle1_interleaving_window": "WINDOW_15M",
        "cycle2_lifecycle_planning_allowed": False,
        "continuation_windows_activated": False,
        "locked_windows": list(LOCKED_WINDOWS),
        "governed_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
        "governed_requests_per_token": LIFECYCLE_REQUESTS_PER_TOKEN,
        "scheduler_row_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
        "automatic_retries": 0,
        "endpoint_rotation": False,
    }


__all__ = [
    "CHECKPOINT_RUNTIME_SECONDS",
    "FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE",
    "LIFECYCLE_REQUESTS_PER_TOKEN",
    "LIFECYCLE_REQUEST_OUTER_CEILING",
    "LIFECYCLE_SCHEDULER_OUTER_CEILING",
    "LOCKED_WINDOWS",
    "MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS",
    "POLICY_VERSION",
    "POST_SUPPLY_LIFECYCLE_DURATION_SECONDS",
    "PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS",
    "TERMINAL_CAUSE",
    "TIMEOUT_CAUSE",
    "exact_admission_checkpoint_policy",
]
