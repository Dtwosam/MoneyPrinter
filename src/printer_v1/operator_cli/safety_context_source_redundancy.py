"""V2-9.6 safety context source redundancy — one backup Solana RPC endpoint.
E.24 replaces the historical uncontracted backup with one fixed governed Helius
Free mainnet endpoint; the old factory name remains for fixture compatibility.

Reduces Solana-RPC transport risk for the holder-concentration authoritative
on-chain field WITHOUT weakening safety evidence. GoPlus remains the primary
provider-risk contributor and is untouched here. The Solana RPC holder call
(which supplements only the authoritative on-chain holder-concentration field
when GoPlus cannot provide it) gets exactly one fixed Helius Free endpoint,
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
  separately persisted and operation-charged, and preserve the primary failure.
- One backup maximum. No retry loops, no recursion, no endpoint rotation.
- The backup only supplies the on-chain holder field. It never fabricates
  GoPlus-only provider-risk fields (mint/freeze authority, LP lock/burn, risk
  flags); missing GoPlus evidence is never relabeled safe, and incomplete or
  conflicting safety stays dirty/blocking in the composite.
"""

from __future__ import annotations

import sqlite3
import inspect
from typing import Any, Callable

from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.helius_holder import HELIUS_SOURCE_NAME


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
    measured_transport_ledger=None,
):
    """Build the fixed Helius Free adapter from an operator-owned key."""
    import os
    from printer_v1.sources.helius_holder import (
        HELIUS_API_KEY_ENV,
        HeliusHolderConfigurationError,
        build_helius_holder_adapter,
        build_helius_holder_transport,
    )
    try:
        transport = build_helius_holder_transport(
            token_mint,
            api_key=os.environ.get(HELIUS_API_KEY_ENV, ""),
            timeout_seconds=timeout_seconds,
            measured_transport_ledger=measured_transport_ledger,
        )
    except HeliusHolderConfigurationError:
        def transport(_context):
            return {
                "fixture_status": "failure",
                "failure_type": "helius_auth_missing",
                "failure_message": "HELIUS_FREE_API_KEY_REQUIRED",
                "underlying_operation_count": 0,
                "transport_operation_identities": [],
                "transport_operations_used": 0,
            }
    return build_helius_holder_adapter(enabled=True, fixture_transport=transport)


def execute_solana_rpc_holder_backup(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step_key: str,
    token_mint: str,
    pair_address: str,
    backup_adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    source_name: str = HELIUS_SOURCE_NAME,
    measured_transport_ledger=None,
) -> Any:
    """Execute exactly one governed Helius Free holder request.

    Separately persisted (its own request/response/failure rows) and separately
    budgeted (Solana RPC's own recent-request window). Returns the governed
    execution result; the caller decides which holder attempt feeds the
    composite (at most one holder contribution).
    """
    request = build_governed_source_request(
        source_name,
        HOLDER_REQUEST_KIND,
        request_key=f"{run_id}:{step_key}:context:holder_backup",
        payload={"token_mint": token_mint, "pair_address": pair_address},
    )
    kwargs = {
        "token_mint": token_mint,
        "timeout_seconds": timeout_seconds,
        "measured_transport_ledger": measured_transport_ledger,
    }
    parameters = inspect.signature(backup_adapter_factory).parameters.values()
    if not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        or parameter.name == "measured_transport_ledger"
        for parameter in parameters
    ):
        kwargs.pop("measured_transport_ledger")
    adapter = backup_adapter_factory(**kwargs)
    return execute_source_request_with_governor(
        conn, request, adapter,
        recent_request_count=count_recent_source_requests(conn, source_name),
    )
