"""Pure, fail-closed campaign identity and state-transition validation.

This module validates identities and campaign lifecycle-state transitions for
the operational memory-factory campaign records defined by migration 031 and
persisted by :mod:`printer_v1.operator_cli.campaign_persistence`.

It performs no persistence, no schema changes, and no database mutation: every
function is a pure validator over already-materialised values or records. It
reuses the campaign/report state vocabulary from ``campaign_persistence`` rather
than introducing a parallel persistence or state system.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from printer_v1.operator_cli.campaign_persistence import (
    CAMPAIGN_STATES,
    TERMINAL_CAMPAIGN_STATES,
)


NON_TERMINAL_CAMPAIGN_STATES = frozenset(
    CAMPAIGN_STATES - TERMINAL_CAMPAIGN_STATES
)

# Identity kinds carried across a campaign's configuration, terminal report,
# and its per-cycle execution identity chain. These are validated for exact
# shape and exact equality; they are never minted or mutated here.
IDENTITY_KINDS = frozenset(
    {
        "campaign",
        "configuration",
        "report",
        "cycle",
        "token_slot",
        "token",
        "mint",
        "pair",
        "lifecycle",
        "window",
        "scheduler_work",
    }
)

_IDENTITY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]*")
_IDENTITY_MAX_LENGTH = 256

# Allowed campaign lifecycle-state transitions. Terminal states are final and
# therefore map to an empty successor set; any attempt to leave a terminal
# state fails closed. Reachability is deliberate: TERMINAL_COMPLETED is only
# reachable once a campaign has actually run.
ALLOWED_CAMPAIGN_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PREFLIGHT", "TERMINAL_BLOCKED", "TERMINAL_FAILED"}),
    "PREFLIGHT": frozenset(
        {
            "RUNNING",
            "TERMINAL_STOPPED",
            "TERMINAL_BLOCKED",
            "TERMINAL_FAILED",
        }
    ),
    "RUNNING": frozenset(
        {
            "STOP_REQUESTED",
            "TERMINAL_COMPLETED",
            "TERMINAL_STOPPED",
            "TERMINAL_BLOCKED",
            "TERMINAL_FAILED",
        }
    ),
    "STOP_REQUESTED": frozenset(
        {
            "TERMINAL_STOPPED",
            "TERMINAL_COMPLETED",
            "TERMINAL_BLOCKED",
            "TERMINAL_FAILED",
        }
    ),
    "TERMINAL_COMPLETED": frozenset(),
    "TERMINAL_STOPPED": frozenset(),
    "TERMINAL_BLOCKED": frozenset(),
    "TERMINAL_FAILED": frozenset(),
}


class CampaignValidationError(ValueError):
    """Base fail-closed campaign identity/state contract violation."""


class CampaignIdentityError(CampaignValidationError):
    """Fail-closed identity shape or identity/predecessor mismatch."""


class CampaignStateError(CampaignValidationError):
    """Fail-closed campaign lifecycle-state contract violation."""


def validate_identity(kind: str, value: Any) -> str:
    """Validate one identity of ``kind`` for exact, safe shape.

    Returns the identity unchanged when valid; raises
    :class:`CampaignIdentityError` otherwise. No normalisation is performed:
    surrounding or embedded whitespace is rejected so that later exact-equality
    checks cannot be defeated by invisible differences.
    """
    if kind not in IDENTITY_KINDS:
        raise CampaignIdentityError(f"unknown identity kind: {kind!r}")
    if not isinstance(value, str):
        raise CampaignIdentityError(f"{kind} identity must be a string")
    if not value:
        raise CampaignIdentityError(f"{kind} identity must be non-empty")
    if len(value) > _IDENTITY_MAX_LENGTH:
        raise CampaignIdentityError(f"{kind} identity is too long")
    if value != value.strip():
        raise CampaignIdentityError(f"{kind} identity has surrounding whitespace")
    if _IDENTITY_PATTERN.fullmatch(value) is None:
        raise CampaignIdentityError(f"{kind} identity has an unsupported shape")
    return value


def require_identity(kind: str, actual: Any, expected: Any) -> str:
    """Validate both identities of ``kind`` and require exact equality."""
    validated_expected = validate_identity(kind, expected)
    validated_actual = validate_identity(kind, actual)
    if validated_actual != validated_expected:
        raise CampaignIdentityError(
            f"{kind} identity mismatch: "
            f"{validated_actual!r} != {validated_expected!r}"
        )
    return validated_actual


def validate_identity_chain(identities: Mapping[str, Any]) -> dict[str, str]:
    """Validate a mapping of ``identity_kind -> identity`` value by value.

    Every key must be a known identity kind and every value must pass
    :func:`validate_identity`. Returns the validated mapping.
    """
    if not isinstance(identities, Mapping):
        raise CampaignIdentityError("identity chain must be a mapping")
    return {
        kind: validate_identity(kind, value)
        for kind, value in identities.items()
    }


def validate_campaign_state(state: Any) -> str:
    """Validate that ``state`` is a known campaign state."""
    if not isinstance(state, str) or state not in CAMPAIGN_STATES:
        raise CampaignStateError(f"unknown campaign state: {state!r}")
    return state


def is_terminal_state(state: Any) -> bool:
    """Return whether ``state`` is a terminal campaign state."""
    return validate_campaign_state(state) in TERMINAL_CAMPAIGN_STATES


def can_transition(from_state: Any, to_state: Any) -> bool:
    """Return whether ``from_state -> to_state`` is an allowed transition."""
    source = validate_campaign_state(from_state)
    target = validate_campaign_state(to_state)
    return target in ALLOWED_CAMPAIGN_TRANSITIONS[source]


def validate_transition(from_state: Any, to_state: Any) -> str:
    """Require that ``from_state -> to_state`` is an allowed transition."""
    source = validate_campaign_state(from_state)
    target = validate_campaign_state(to_state)
    if target not in ALLOWED_CAMPAIGN_TRANSITIONS[source]:
        raise CampaignStateError(
            f"campaign transition not allowed: {source} -> {target}"
        )
    return target


@dataclass(frozen=True)
class Terminalization:
    """Result of a terminalization request.

    ``changed`` is ``False`` when the request is an idempotent replay of an
    already-recorded terminalization.
    """

    state: str
    first_terminal_cause: str
    changed: bool


def terminalize(
    *,
    current_state: Any,
    current_first_terminal_cause: Any,
    requested_state: Any,
    requested_first_terminal_cause: Any,
) -> Terminalization:
    """Validate a campaign terminalization, fail-closed and idempotent.

    The requested terminal state must be a terminal state whose transition from
    the current non-terminal state is allowed. Repeating an identical
    terminalization is idempotent (``changed=False``). Once terminal, the first
    terminal cause is immutable and the terminal state cannot change: any
    divergent request fails closed.
    """
    requested = validate_campaign_state(requested_state)
    if requested not in TERMINAL_CAMPAIGN_STATES:
        raise CampaignStateError(
            f"requested state is not terminal: {requested}"
        )
    if (
        not isinstance(requested_first_terminal_cause, str)
        or not requested_first_terminal_cause.strip()
    ):
        raise CampaignStateError("first terminal cause must be a non-empty string")

    current = validate_campaign_state(current_state)

    if current in TERMINAL_CAMPAIGN_STATES:
        if not isinstance(current_first_terminal_cause, str) or not (
            current_first_terminal_cause.strip()
        ):
            raise CampaignStateError(
                "terminal campaign is missing its first terminal cause"
            )
        if requested != current:
            raise CampaignStateError(
                "campaign is already terminal in a different state: "
                f"{current} != {requested}"
            )
        if requested_first_terminal_cause != current_first_terminal_cause:
            raise CampaignStateError("first terminal cause is immutable")
        return Terminalization(
            state=current,
            first_terminal_cause=current_first_terminal_cause,
            changed=False,
        )

    # Non-terminal current state: the terminal transition must be allowed and no
    # prior terminal cause may exist yet.
    if (
        current_first_terminal_cause is not None
        and str(current_first_terminal_cause).strip()
    ):
        raise CampaignStateError(
            "non-terminal campaign must not carry a first terminal cause"
        )
    validate_transition(current, requested)
    return Terminalization(
        state=requested,
        first_terminal_cause=requested_first_terminal_cause,
        changed=True,
    )


def validate_report_predecessor(
    *,
    replay_campaign_id: Any,
    replay_configuration_id: Any,
    predecessor_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a replay's predecessor terminal-report reference, fail-closed.

    ``predecessor_report`` is a persisted campaign-report record (as produced by
    :func:`printer_v1.operator_cli.campaign_persistence.persist_terminal_report`).
    A replay may only reference a ``TERMINAL`` report in the ``REPORT_TERMINAL``
    state that belongs to exactly the same campaign and configuration.
    """
    if not isinstance(predecessor_report, Mapping):
        raise CampaignIdentityError("predecessor report must be a record mapping")

    kind = predecessor_report.get("report_kind")
    if kind != "TERMINAL":
        raise CampaignIdentityError(
            f"predecessor report must be TERMINAL, got {kind!r}"
        )
    state = predecessor_report.get("report_state")
    if state != "REPORT_TERMINAL":
        raise CampaignIdentityError(
            f"predecessor report must be REPORT_TERMINAL, got {state!r}"
        )

    require_identity(
        "campaign",
        replay_campaign_id,
        predecessor_report.get("campaign_id"),
    )
    require_identity(
        "configuration",
        replay_configuration_id,
        predecessor_report.get("configuration_id"),
    )
    validate_identity("report", predecessor_report.get("report_id"))
    return dict(predecessor_report)
