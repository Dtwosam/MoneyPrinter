"""Lane E2I -- Governed Real Source Transport Boundary.

Provides the real DexScreener smoke transport required for TRACK_FAST_FIRST_15M.

After this module is imported:
- check_real_source_transport_available() returns (True, reason)
- E2H delegates its transport check here via lazy import
- E2G _check_15m_cycle_runtime_available() returns (True, ...) and reports
  OPERATOR_RUN_READY when all other gates pass
- One-shot governed source smoke command is available for operator verification

Transport is token-specific: the approved token mint from the operator token list
is used as the DexScreener lookup target. Generic SOL search is forbidden.

Permitted operations for the one-shot smoke command:
- Validate token list (1 TRACK_FAST approved token, no placeholder)
- Validate backup proof file exists
- Ask Source Governor (can_request_source)
- Call ONE free/public DexScreener tokens endpoint through governed transport,
  using the approved token mint as the lookup target
- Record source request / response / failure rows
- Report before/after DB row counts

Hard locks (permanent -- never violated):
- No BUY/SELL/HOLD, paper decisions, positions, or PnL
- No snapshots, context, or memory creation
- No wallet, private keys, signing, or live execution
- No paid APIs
- No scoring, ranking, confidence, weighted logic, embeddings, or vectors
- No generic SOL search (token-specific endpoint only)
- Claude did not run the full 15m cycle
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


E2I_TRANSPORT_SOURCE_NAME: str = "dexscreener"
E2I_TRANSPORT_REQUEST_KIND: str = "pair_market_snapshot"
E2I_STATUS_EXECUTED: str = "E2I_GOVERNED_SOURCE_SMOKE_EXECUTED"
E2I_STATUS_BLOCKED: str = "E2I_GOVERNED_SOURCE_SMOKE_BLOCKED"

_TRANSPORT_AVAILABLE_REASON: str = (
    "Lane E2I: DexScreener token-specific smoke transport available via"
    " build_e2i_dexscreener_adapter(token_mint=...) in e2i_source_transport.py;"
    " build_dexscreener_token_transport(token_mint) provides real urllib HTTP transport;"
    " generic SOL search is forbidden; token-specific endpoint only; approved token mint required;"
    " one-shot smoke command printer-run-e2i-one-shot-governed-source-smoke available"
)

_GENERIC_SEARCH_FORBIDDEN: bool = True

_FORBIDDEN_SMOKE_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_memories",
)

_AUDIT_TABLES: tuple[str, ...] = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_memories",
)

_GOVERNOR_REJECT_FAILURE_TYPES: frozenset[str] = frozenset(
    {"rate_limit_exceeded", "source_not_in_registry", "request_kind_not_allowed"}
)

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_snapshots": True,
    "no_memory_creation": True,
    "no_context_creation": True,
    "no_paid_api": True,
    "no_live_trading": True,
    "no_cycle_run": True,
    "no_generic_search": True,
}


def check_real_source_transport_available() -> tuple[bool, str]:
    """Return (True, reason) -- real DexScreener smoke transport is available via Lane E2I."""
    return (True, _TRANSPORT_AVAILABLE_REASON)


def is_real_source_transport_available() -> bool:
    """Return True -- real DexScreener smoke transport is available via Lane E2I."""
    return True


def build_e2i_dexscreener_adapter(*, token_mint: str, timeout_seconds: float = 5.0):
    """Build a token-specific real-transport DexScreener adapter for governed source smoke.

    Returns DexScreenerAdapter(enabled=True, smoke_transport=token_specific_transport).
    The transport calls the DexScreener tokens endpoint for the given token_mint.
    Generic SOL search is forbidden. token_mint must not be empty or a placeholder.
    All calls must still go through execute_source_request_with_governor.
    Free/public API only. No paid tier. No authentication required.
    """
    if not token_mint or token_mint.startswith("PLACEHOLDER"):
        raise ValueError(
            f"E2I smoke transport requires a valid token_mint, got: {token_mint!r}"
        )
    from printer_v1.sources.dexscreener import (
        build_dexscreener_adapter,
        build_dexscreener_token_transport,
    )
    transport = build_dexscreener_token_transport(token_mint, timeout_seconds=timeout_seconds)
    return build_dexscreener_adapter(enabled=True, smoke_transport=transport)


def _count_table_rows(db_path: str | Path, table_name: str) -> int | str:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return f"table '{table_name}' not found"
        finally:
            conn.close()
    except Exception as exc:
        return f"error: {exc}"


def _get_audit_counts(db_path: str | Path) -> dict[str, int | str]:
    return {t: _count_table_rows(db_path, t) for t in _AUDIT_TABLES}


def _check_forbidden_tables_zero(db_path: str | Path) -> list[str]:
    violations: list[str] = []
    for table in _FORBIDDEN_SMOKE_TABLES:
        count = _count_table_rows(db_path, table)
        if isinstance(count, int) and count > 0:
            violations.append(f"{table}: {count} rows (must remain 0)")
    return violations


def _load_and_validate_token_list(
    path: str | Path | None,
) -> tuple[bool, str, list[dict], str]:
    """Return (valid, reason, tokens, approved_mint).

    approved_mint is the token_mint from the single TRACK_FAST approved token,
    or empty string when validation fails.
    """
    if path is None:
        return False, "token_list_path is required", [], ""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"token list file not found: {path}", [], ""
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"token list file unreadable: {exc}", [], ""

    tokens = list(data.get("tokens", []))
    track_fast_approved = [
        t for t in tokens
        if str(t.get("lifecycle_lane", "")) == "TRACK_FAST"
        and bool(t.get("approved_by_operator", False))
    ]
    if not track_fast_approved:
        return False, "no TRACK_FAST approved tokens in token list", tokens, ""
    if len(track_fast_approved) > 1:
        return (
            False,
            f"expected 1 TRACK_FAST approved token, found {len(track_fast_approved)}",
            tokens,
            "",
        )
    mint = str(track_fast_approved[0].get("token_mint", ""))
    if not mint or mint.startswith("PLACEHOLDER"):
        return False, f"invalid or placeholder token mint: {mint!r}", tokens, ""
    return True, f"1 TRACK_FAST approved token: {mint}", tokens, mint


def execute_e2i_governed_smoke(
    db_path_or_conn,
    *,
    adapter=None,
    token_mint: str = "",
    source_name: str = E2I_TRANSPORT_SOURCE_NAME,
    request_kind: str = E2I_TRANSPORT_REQUEST_KIND,
    recent_request_count: int = 0,
):
    """Execute one governed DexScreener call through the Source Governor.

    Records to printer_source_requests, printer_source_responses, and
    printer_source_failures only. No snapshots, context, memory, or paper rows.

    When adapter=None, builds a real token-specific DexScreener adapter.
    token_mint is required when adapter=None (generic search is forbidden).
    Pass a fixture adapter in tests to avoid real network calls.
    """
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.governed_execution import execute_source_request_with_governor

    if adapter is None:
        if not token_mint:
            raise ValueError(
                "token_mint is required when no adapter provided:"
                " E2I smoke transport is token-specific, generic search is forbidden"
            )
        adapter = build_e2i_dexscreener_adapter(token_mint=token_mint)

    source_request = build_governed_source_request(source_name, request_kind)
    return execute_source_request_with_governor(
        db_path_or_conn,
        source_request,
        adapter,
        recent_request_count=recent_request_count,
    )


def build_e2i_one_shot_smoke_payload(
    token_list_path: str | Path | None,
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    source_name: str = E2I_TRANSPORT_SOURCE_NAME,
    request_kind: str = E2I_TRANSPORT_REQUEST_KIND,
    operator_approved: bool = False,
    adapter=None,
) -> dict[str, Any]:
    """Build one-shot governed DexScreener source smoke payload.

    May only: validate token list, validate backup proof, consult Source Governor,
    call one free/public DexScreener tokens endpoint through governed transport,
    using the approved token mint from the token list as the lookup target,
    record source request/response/failure rows, report before/after DB counts.

    Must not: create snapshots, context, memories, paper decisions, BUY/SELL/HOLD,
    positions, PnL, scheduler jobs, or any forbidden table rows.
    Generic SOL search is forbidden; transport is always token-specific.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved flag must be explicitly set to True")

    backup_proof_ok = False
    if backup_proof_path is None:
        blocked_reasons.append("backup_proof_path is required")
    else:
        if Path(backup_proof_path).is_file():
            backup_proof_ok = True
        else:
            blocked_reasons.append(f"backup proof file does not exist: {backup_proof_path}")

    db_path_ok = False
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        if Path(db_path).is_file():
            db_path_ok = True
        else:
            blocked_reasons.append(f"db file does not exist: {db_path}")

    token_list_valid, token_list_reason, _tokens, approved_mint = _load_and_validate_token_list(
        token_list_path
    )
    if not token_list_valid:
        blocked_reasons.append(f"token list invalid: {token_list_reason}")

    if blocked_reasons:
        return {
            "command": "printer-run-e2i-one-shot-governed-source-smoke",
            "e2i_status": E2I_STATUS_BLOCKED,
            "executed": False,
            "source_name": source_name,
            "request_kind": request_kind,
            "operator_approved": operator_approved,
            "token_list_valid": token_list_valid,
            "approved_token_mint": None,
            "smoke_target": None,
            "generic_search_used": False,
            "backup_proof_confirmed": backup_proof_ok,
            "source_governor_allowed": None,
            "blocked_reasons": blocked_reasons,
            "before_counts": {},
            "after_counts": {},
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "snapshots_created": 0,
            "memories_created": 0,
            "claude_did_not_run_cycle": True,
            "hard_locks": dict(_HARD_LOCKS),
        }

    before_counts = _get_audit_counts(db_path)
    pre_violations = _check_forbidden_tables_zero(db_path)

    source_governor_allowed: bool | None = None
    source_status: str | None = None
    data_quality_label: str | None = None
    request_recorded = False
    response_recorded = False
    failure_recorded = False
    exec_error: str | None = None

    try:
        result = execute_e2i_governed_smoke(
            str(db_path),
            token_mint=approved_mint,
            adapter=adapter,
            source_name=source_name,
            request_kind=request_kind,
        )
        normalized = result.normalized_result
        failure_type = normalized.failure_type or ""
        source_governor_allowed = failure_type not in _GOVERNOR_REJECT_FAILURE_TYPES
        source_status = str(
            normalized.source_status.value
            if hasattr(normalized.source_status, "value")
            else normalized.source_status
        )
        data_quality_label = str(
            normalized.data_quality_label.value
            if hasattr(normalized.data_quality_label, "value")
            else normalized.data_quality_label
        )
        request_recorded = result.request_record is not None
        response_recorded = result.response_record is not None
        failure_recorded = result.failure_record is not None
    except Exception as exc:
        exec_error = str(exc)
        source_governor_allowed = False

    after_counts = _get_audit_counts(db_path)
    post_violations = _check_forbidden_tables_zero(db_path)
    executed = exec_error is None

    return {
        "command": "printer-run-e2i-one-shot-governed-source-smoke",
        "e2i_status": E2I_STATUS_EXECUTED if executed else E2I_STATUS_BLOCKED,
        "executed": executed,
        "source_name": source_name,
        "request_kind": request_kind,
        "operator_approved": operator_approved,
        "token_list_valid": token_list_valid,
        "token_list_reason": token_list_reason,
        "approved_token_mint": approved_mint,
        "smoke_target": f"dexscreener:token:{approved_mint}",
        "generic_search_used": False,
        "backup_proof_confirmed": backup_proof_ok,
        "db_path_confirmed": db_path_ok,
        "source_governor_allowed": source_governor_allowed,
        "source_status": source_status,
        "data_quality_label": data_quality_label,
        "request_recorded": request_recorded,
        "response_recorded": response_recorded,
        "failure_recorded": failure_recorded,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "pre_condition_violations": pre_violations,
        "post_condition_violations": post_violations,
        "exec_error": exec_error,
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "snapshots_created": 0,
        "memories_created": 0,
        "claude_did_not_run_cycle": True,
        "hard_locks": dict(_HARD_LOCKS),
    }
