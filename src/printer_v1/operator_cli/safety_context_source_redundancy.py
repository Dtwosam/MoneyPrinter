"""V2-9.6 safety context source redundancy — one backup Solana RPC endpoint.

Reduces Solana-RPC transport risk for the holder-concentration authoritative
on-chain field WITHOUT weakening safety evidence. GoPlus remains the primary
provider-risk contributor and is untouched here. The Solana RPC holder call
(which supplements only the authoritative on-chain holder-concentration field
when GoPlus cannot provide it) gets exactly ONE governed backup endpoint,
attempted at most once, and only after an eligible transient primary-RPC
failure.

Governance:
- Backup is attempted only for transient transport failures: TLS/connection
  interruption, connect/read timeout, HTTP 429, or temporary HTTP 5xx.
- Never for malformed/non-object responses, parser defects, HTTP 4xx, RPC-level
  data errors, identity mismatch, stale/conflicting data, or governor/budget
  rejections.
- Both attempts pass through the Source Governor, remain Central-Scheduler
  owned (they run inside the already-scheduled window-close context step), are
  separately persisted and budgeted, and preserve the original primary failure.
- One backup maximum. No retry loops, no recursion, no endpoint rotation.
- The backup only supplies the on-chain holder field. It never fabricates
  GoPlus-only provider-risk fields (mint/freeze authority, LP lock/burn, risk
  flags); missing GoPlus evidence is never relabeled safe, and incomplete or
  conflicting safety stays dirty/blocking in the composite.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.solana_rpc_holder import SOLANA_RPC_SOURCE_NAME


HOLDER_REQUEST_KIND = "holder_concentration_reference"

# Primary Solana-RPC holder failure types that are transient and backup-eligible.
# Everything not in this set (malformed/non-object response, parser defect,
# HTTP 4xx client error, RPC-level data error, governor/budget rejection) is
# NOT eligible.
ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES: frozenset[str] = frozenset({
    "solana_rpc_transport_failure",   # TLS/connection interruption, connect/read timeout
    "solana_rpc_http_server_error",   # temporary HTTP 5xx
    "solana_rpc_rate_limited",        # HTTP 429
})


def is_eligible_transient_solana_rpc_failure(execution: Any) -> bool:
    """Return True only for a genuine, transient primary holder-RPC failure.

    Requires the primary reached the provider and failed there (a failure record
    with no response record) with a failure type in the eligible allowlist.
    Governor rejections also produce a failure record with no response, but their
    failure types are not in the allowlist, so they are excluded.
    """
    if execution is None:
        return False
    if getattr(execution, "response_record", None) is not None:
        return False
    if getattr(execution, "failure_record", None) is None:
        return False
    failure_type = getattr(execution.normalized_result, "failure_type", None)
    return failure_type in ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES


def build_default_solana_rpc_holder_backup_adapter(
    *, token_mint: str, timeout_seconds: float = 10.0,
):
    """Build a real, governed Solana-RPC holder adapter bound to the backup endpoint.

    Free/public, keyless, read-only single backup endpoint. All execution still
    flows through execute_source_request_with_governor. Tests inject a fixture
    adapter instead of calling this.
    """
    from printer_v1.sources.solana_rpc_holder import (
        SOLANA_PUBLIC_RPC_BACKUP_URL,
        build_solana_rpc_holder_adapter,
        build_solana_rpc_holder_transport,
    )

    transport = build_solana_rpc_holder_transport(
        token_mint, rpc_url=SOLANA_PUBLIC_RPC_BACKUP_URL, timeout_seconds=timeout_seconds,
    )
    return build_solana_rpc_holder_adapter(enabled=True, fixture_transport=transport)


def execute_solana_rpc_holder_backup(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step_key: str,
    token_mint: str,
    pair_address: str,
    backup_adapter_factory: Callable[..., Any],
    timeout_seconds: float,
) -> Any:
    """Execute exactly one governed backup Solana-RPC holder request.

    Separately persisted (its own request/response/failure rows) and separately
    budgeted (Solana RPC's own recent-request window). Returns the governed
    execution result; the caller decides which holder attempt feeds the
    composite (at most one holder contribution).
    """
    request = build_governed_source_request(
        SOLANA_RPC_SOURCE_NAME,
        HOLDER_REQUEST_KIND,
        request_key=f"{run_id}:{step_key}:context:holder_backup",
        payload={"token_mint": token_mint, "pair_address": pair_address},
    )
    adapter = backup_adapter_factory(token_mint=token_mint, timeout_seconds=timeout_seconds)
    return execute_source_request_with_governor(
        conn, request, adapter,
        recent_request_count=count_recent_source_requests(conn, SOLANA_RPC_SOURCE_NAME),
    )
