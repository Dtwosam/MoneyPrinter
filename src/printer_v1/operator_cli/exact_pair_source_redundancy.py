"""V2-9.5 unified exact-pair snapshot source redundancy.

Removes DexScreener as a single point of failure for the mandatory exact-pair
market snapshot by adding one governed GeckoTerminal fallback that is attempted
**at most once**, and only after an *eligible transient* DexScreener transport
failure.

Governance (all enforced here and by the Source Governor):
- DexScreener remains primary; GeckoTerminal is a fallback, never a rotation.
- Fallback is attempted only for transient transport failures: TLS/connection
  interruption, connect/read timeout, HTTP 429, or temporary HTTP 5xx.
- Never for malformed payloads, parser/schema defects, stale or conflicting
  data, token/pair mismatch, missing mandatory fields, or governor/budget
  rejections.
- Both attempts pass through the Source Governor, remain Central-Scheduler
  owned (called inside the scheduled step), are separately persisted and
  budgeted, and preserve the original primary failure.
- No retry loops, no recursion, no endpoint rotation. Fail closed if the
  fallback is invalid or also fails.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.geckoterminal import (
    GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND,
    GECKOTERMINAL_SOURCE_NAME,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor


# Primary DexScreener failure types that are transient and fallback-eligible.
# Everything not in this set (malformed payload, parser defect, HTTP 4xx client
# error, governor/budget rejection, identity/field problems) is NOT eligible.
ELIGIBLE_TRANSIENT_PRIMARY_FAILURE_TYPES: frozenset[str] = frozenset({
    "dexscreener_transport_failure",     # TLS/connection interruption, connect/read timeout
    "dexscreener_http_server_error",     # temporary HTTP 5xx
    "dexscreener_rate_limited_fixture",  # DexScreener HTTP 429
})

FALLBACK_SOURCE_NAME: str = GECKOTERMINAL_SOURCE_NAME
FALLBACK_REQUEST_KIND: str = GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND


def is_eligible_transient_primary_failure(execution: Any) -> bool:
    """Return True only for a genuine, transient primary transport failure.

    Requires that the primary reached the provider and failed there (a failure
    record with no response record), and that the failure type is in the
    eligible transient allowlist. Governor rejections (which also produce a
    failure record with no response) are excluded because their failure types
    are not in the allowlist.
    """
    if execution is None:
        return False
    if getattr(execution, "response_record", None) is not None:
        return False
    if getattr(execution, "failure_record", None) is None:
        return False
    failure_type = getattr(execution.normalized_result, "failure_type", None)
    return failure_type in ELIGIBLE_TRANSIENT_PRIMARY_FAILURE_TYPES


def build_default_geckoterminal_fallback_adapter(
    *, pair_address: str, token_mint: str, timeout_seconds: float = 8.0,
):
    """Build a real, governed GeckoTerminal exact-pair snapshot adapter.

    Free/public single-pool endpoint only. All execution still flows through
    execute_source_request_with_governor. Tests inject a fixture adapter
    instead of calling this.
    """
    from printer_v1.sources.geckoterminal import (
        build_geckoterminal_adapter,
        build_geckoterminal_pair_snapshot_transport,
    )

    transport = build_geckoterminal_pair_snapshot_transport(
        pair_address, token_mint, timeout_seconds=timeout_seconds,
    )
    return build_geckoterminal_adapter(enabled=True, fixture_transport=transport)


def execute_geckoterminal_fallback(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    fallback_adapter_factory: Callable[..., Any],
    timeout_seconds: float,
) -> Any:
    """Execute exactly one governed GeckoTerminal exact-pair snapshot request.

    Separately persisted (its own request/response/failure rows) and separately
    budgeted (GeckoTerminal's own recent-request window). Returns the governed
    execution result; the caller decides whether to persist from it.
    """
    mint = str(step["token_mint"])
    pair_address = str(step["pair_address"])
    request = build_governed_source_request(
        FALLBACK_SOURCE_NAME,
        FALLBACK_REQUEST_KIND,
        request_key=f"{step['run_id']}:{step['step_key']}:geckoterminal_fallback",
        payload={"pool_address": pair_address, "token_mint": mint},
    )
    adapter = fallback_adapter_factory(
        pair_address=pair_address, token_mint=mint, timeout_seconds=timeout_seconds,
    )
    return execute_source_request_with_governor(
        conn, request, adapter,
        recent_request_count=count_recent_source_requests(conn, FALLBACK_SOURCE_NAME),
    )
