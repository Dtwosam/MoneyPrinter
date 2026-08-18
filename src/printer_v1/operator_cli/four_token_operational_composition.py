"""Neutral operational 4/2/2 composition facade for V2-9.8B.

This module exists so operational production code can express the approved
four-token / two-cycle / two-slots-per-cycle authority without depending on
proof-named wrapper semantics. It is an authority/wiring layer only.

It owns no numbers: every ceiling is projected from the one canonical
``scaled_standard_four_hour_capacity_contract(4)`` authority, which itself
derives from the canonical two-token standard-four-hour lifecycle arithmetic.

It builds no runtime: the multi-cycle controller it returns is exactly the
already-repaired canonical composition. It creates no second Memory Factory
runner, no second Central Scheduler, no second Source Governor, no independent
provider/source loop, no separate schema owner, and no separate candidate
selection algorithm.

It performs no I/O of any kind: no network request, no database connection, no
file creation, and no process start.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from printer_v1.operator_cli.four_token_factory_adapter import (
    validate_second_cycle_atomic_activation as validate_later_cycle_atomic_activation,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenProofController,
    )


#: The one explicit operational four-token command mode. It is not a proof
#: label and not a capacity selector: it has exactly one immutable shape.
FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE = "four-token-standard-four-hour-run"

#: Distinct from both ``V2-9.8-STANDARD-4H-OPERATIONAL-V1`` (the existing
#: two-token authority) and ``V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1``
#: (the existing proof-only authority).
POLICY_VERSION = "V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1"

#: The one derived numeric authority for this whole operational lane.
OPERATIONAL_CAPACITY = scaled_standard_four_hour_capacity_contract(4)

CONFIGURED_THROUGH_4H_TOKENS = int(
    OPERATIONAL_CAPACITY["configured_through_4h_tokens"]
)
CONFIGURED_ACTIVE_CYCLES = int(OPERATIONAL_CAPACITY["configured_active_cycles"])
TOTAL_CYCLE_ADMISSION_CEILING = CONFIGURED_ACTIVE_CYCLES
TOKENS_PER_CYCLE = int(OPERATIONAL_CAPACITY["tokens_per_cycle"])
MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS = int(
    OPERATIONAL_CAPACITY["minimum_cycle_admission_spacing_seconds"]
)
SHARED_DISCOVERY_REQUESTS = int(OPERATIONAL_CAPACITY["shared_discovery_requests"])
LIFECYCLE_REQUEST_OUTER_CEILING = int(
    OPERATIONAL_CAPACITY["lifecycle_request_outer_ceiling"]
)
LIFECYCLE_REQUESTS_PER_TOKEN = int(
    OPERATIONAL_CAPACITY["lifecycle_requests_per_token"]
)
LIFECYCLE_SCHEDULER_OUTER_CEILING = int(
    OPERATIONAL_CAPACITY["lifecycle_scheduler_outer_ceiling"]
)

#: Window law. 15m is the one root main window; 1h and 4h are the only lawful
#: continuations; 5m stays support-only and creates no continuation authority;
#: 12h and 24h remain locked until their own separately gated lanes.
ROOT_MAIN_WINDOW = "WINDOW_15M"
MAIN_LIFECYCLE_WINDOWS = ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H")
SUPPORT_ONLY_WINDOW = "WINDOW_5M_MICRO_EVENT"
LOCKED_WINDOWS = ("WINDOW_12H", "WINDOW_24H")

#: The two bounded clocks stay separate and raise no provider rate ceiling and
#: create no retry authority. They only give the second fresh cycle and its
#: through-4h lifecycle a finite same-invocation wall-time envelope. They are
#: the proven four-token bounded clocks, reused rather than re-derived.
PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = 2_400
POST_SUPPLY_LIFECYCLE_DURATION_SECONDS = 18_000
MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS = (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
    + POST_SUPPLY_LIFECYCLE_DURATION_SECONDS
)


def exact_operational_policy() -> dict[str, Any]:
    """Return the one exact 4/2/2 operational policy this authority may bind.

    Every value is read from the derived capacity constants above, so a widened
    capacity, a third cycle, a single-token cycle, shortened spacing, a copied
    two-token ceiling, a retry, endpoint rotation or a long window cannot be
    expressed here at all.
    """
    return {
        "policy_version": POLICY_VERSION,
        "configured_through_4h_tokens": CONFIGURED_THROUGH_4H_TOKENS,
        "configured_active_cycles": CONFIGURED_ACTIVE_CYCLES,
        "total_cycle_admission_ceiling": TOTAL_CYCLE_ADMISSION_CEILING,
        "tokens_per_cycle": TOKENS_PER_CYCLE,
        "minimum_cycle_admission_spacing_seconds": (
            MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS
        ),
        "standard_four_hour_campaign": True,
        "root_main_window": ROOT_MAIN_WINDOW,
        "pre_lifecycle_acquisition_duration_seconds": (
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
        ),
        "post_supply_lifecycle_duration_seconds": (
            POST_SUPPLY_LIFECYCLE_DURATION_SECONDS
        ),
        "shared_discovery_requests": SHARED_DISCOVERY_REQUESTS,
        "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
        "lifecycle_requests_per_token": LIFECYCLE_REQUESTS_PER_TOKEN,
        "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "long_windows_activated": False,
        "locked_windows": list(LOCKED_WINDOWS),
    }


def build_operational_multi_cycle_controller() -> "FourTokenProofController":
    """Return the already-repaired canonical multi-cycle controller.

    The import is local so this facade stays a thin authority layer and never
    becomes a second composition root. The controller and its policy are the
    existing proven primitives: this function selects them, it does not
    redefine, wrap, widen or replace them.
    """
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenProofController,
    )

    return FourTokenProofController.exact()


__all__ = [
    "CONFIGURED_ACTIVE_CYCLES",
    "CONFIGURED_THROUGH_4H_TOKENS",
    "FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE",
    "LIFECYCLE_REQUESTS_PER_TOKEN",
    "LIFECYCLE_REQUEST_OUTER_CEILING",
    "LIFECYCLE_SCHEDULER_OUTER_CEILING",
    "LOCKED_WINDOWS",
    "MAIN_LIFECYCLE_WINDOWS",
    "MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS",
    "MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS",
    "OPERATIONAL_CAPACITY",
    "POLICY_VERSION",
    "POST_SUPPLY_LIFECYCLE_DURATION_SECONDS",
    "PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS",
    "ROOT_MAIN_WINDOW",
    "SHARED_DISCOVERY_REQUESTS",
    "SUPPORT_ONLY_WINDOW",
    "TOKENS_PER_CYCLE",
    "TOTAL_CYCLE_ADMISSION_CEILING",
    "build_operational_multi_cycle_controller",
    "exact_operational_policy",
    "validate_later_cycle_atomic_activation",
]
