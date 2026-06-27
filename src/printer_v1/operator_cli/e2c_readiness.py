"""E2C Active Cycle Readiness Package -- dry-run/planning helpers.

All functions are read-only: no DB mutation, no source fetching, no paper decisions,
no scheduler execution, no memory creation, no retrieval activation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.governor import can_request_source
from printer_v1.sources.registry import SOURCE_REGISTRY


# Solana base58 alphabet: excludes 0, O, I, l to prevent visual ambiguity.
SOLANA_BASE58_ALPHABET: frozenset[str] = frozenset(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)

VALID_LIFECYCLE_LANES: frozenset[str] = frozenset({"TRACK_FAST", "TRACK_NORMAL"})

MIN_TOKEN_COUNT: int = 1
MAX_TOKEN_COUNT: int = 2
MAX_ACTIVE_TOKENS: int = 10
MAX_TRACK_FAST: int = 3
MAX_TRACK_NORMAL: int = 7

RECOMMENDATION_BLOCKED: str = "BLOCKED"
RECOMMENDATION_LIMITED_GO: str = "LIMITED_GO_FOR_OPERATOR_REVIEW"

HARD_LOCKS: dict[str, bool] = {
    "source_fetching_enabled": False,
    "scheduler_execution_enabled": False,
    "snapshot_creation_enabled": False,
    "memory_creation_enabled": False,
    "retrieval_activation_enabled": False,
    "paper_decisions_enabled": False,
    "buy_enabled": False,
    "sell_enabled": False,
    "hold_enabled": False,
    "positions_enabled": False,
    "pnl_enabled": False,
}


def is_valid_solana_mint(mint: str) -> bool:
    """Return True if mint is structurally valid as a Solana base58 address (43-44 chars)."""
    if not isinstance(mint, str):
        return False
    return 43 <= len(mint) <= 44 and all(c in SOLANA_BASE58_ALPHABET for c in mint)


def validate_token_list(tokens: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate operator-approved token entries for a first bounded E2C cycle.

    Each entry requires:
      token_mint     -- Solana base58 address (43-44 chars, base58 alphabet only)
      lifecycle_lane -- TRACK_FAST or TRACK_NORMAL

    Returns {"valid", "errors", "token_count", "tokens"}.
    Tokens list is populated only when valid is True.
    """
    errors: list[str] = []
    token_count = len(tokens)

    if token_count < MIN_TOKEN_COUNT:
        return {
            "valid": False,
            "errors": [
                f"token list requires at least {MIN_TOKEN_COUNT} entry; got {token_count}"
            ],
            "token_count": token_count,
            "tokens": [],
        }

    if token_count > MAX_TOKEN_COUNT:
        return {
            "valid": False,
            "errors": [
                f"token list allows at most {MAX_TOKEN_COUNT} entries; got {token_count}"
            ],
            "token_count": token_count,
            "tokens": [],
        }

    seen_mints: set[str] = set()
    for i, entry in enumerate(tokens):
        mint = str(entry.get("token_mint", ""))
        lane = str(entry.get("lifecycle_lane", ""))

        if mint in seen_mints:
            errors.append(f"duplicate token_mint at index {i}: {mint!r}")
        else:
            seen_mints.add(mint)

        if not is_valid_solana_mint(mint):
            errors.append(
                f"token[{i}].token_mint {mint!r} is not a valid Solana base58 mint"
                " (43-44 chars, base58 alphabet only)"
            )

        if lane not in VALID_LIFECYCLE_LANES:
            errors.append(
                f"token[{i}].lifecycle_lane {lane!r} is not supported;"
                " must be TRACK_FAST or TRACK_NORMAL"
            )

    if errors:
        return {"valid": False, "errors": errors, "token_count": token_count, "tokens": []}

    return {
        "valid": True,
        "errors": [],
        "token_count": token_count,
        "tokens": [
            {"token_mint": t["token_mint"], "lifecycle_lane": t["lifecycle_lane"]}
            for t in tokens
        ],
    }


def check_db_preflight(
    db_path: str | Path | None,
    *,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Read-only DB pre-cycle preflight check. Never mutates the database.

    Checks:
    - db_path provided and exists
    - backup_confirmed flag
    - zero RUNNING jobs in printer_scheduler_jobs
    - zero active locks (locked_at IS NOT NULL)

    Returns {"db_path", "db_path_exists", "backup_confirmed",
             "running_jobs", "active_locks", "preflight_passed", "errors"}.
    """
    if db_path is None:
        return {
            "db_path": None,
            "db_path_exists": False,
            "backup_confirmed": backup_confirmed,
            "running_jobs": None,
            "active_locks": None,
            "preflight_passed": False,
            "errors": ["no db_path provided; cannot confirm pre-cycle DB state"],
        }

    resolved = Path(db_path)
    exists = resolved.exists()
    errors: list[str] = []

    if not exists:
        errors.append(f"db_path does not exist: {resolved}")

    if not backup_confirmed:
        errors.append("backup_confirmed is False; DB backup must be confirmed before cycle")

    running_jobs: int | None = None
    active_locks: int | None = None

    if exists:
        try:
            conn = sqlite3.connect(str(resolved))
            try:
                running_jobs = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
                    ).fetchone()[0]
                )
                active_locks = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM printer_scheduler_jobs"
                        " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
                    ).fetchone()[0]
                )
            finally:
                conn.close()
        except Exception as exc:
            errors.append(f"DB query failed: {exc}")
        else:
            if running_jobs is not None and running_jobs > 0:
                errors.append(
                    f"{running_jobs} RUNNING job(s) in printer_scheduler_jobs; must be 0"
                )
            if active_locks is not None and active_locks > 0:
                errors.append(
                    f"{active_locks} active lock(s) in printer_scheduler_jobs; must be 0"
                )

    return {
        "db_path": str(resolved),
        "db_path_exists": exists,
        "backup_confirmed": backup_confirmed,
        "running_jobs": running_jobs,
        "active_locks": active_locks,
        "preflight_passed": not errors,
        "errors": errors,
    }


def plan_source_budget(db_path: str | Path | None) -> dict[str, Any]:
    """Plan source budget for all non-paid sources.

    Uses count_recent_source_requests (E2C-B budget accounting, read-only) to
    compute recent consumed attempts per source, then feeds each count to
    can_request_source (Source Governor) to produce per-source allowed/blocked decisions.

    Never fetches sources. Never mutates the database.
    """
    window_seconds: int = 60
    planned: list[dict[str, Any]] = []

    for source_name, defn in SOURCE_REGISTRY.items():
        if defn.requires_paid_plan:
            continue

        recent_count = 0
        if db_path is not None:
            resolved = Path(db_path)
            if resolved.exists():
                try:
                    recent_count = count_recent_source_requests(
                        resolved, source_name, window_seconds=window_seconds
                    )
                except Exception as exc:
                    planned.append({
                        "source_name": source_name,
                        "representative_request_kind": defn.allowed_request_kinds[0],
                        "recent_request_count": None,
                        "rate_limit_per_minute": defn.default_rate_limit_per_minute,
                        "governor_decision": "budget_accounting_error",
                        "allowed": False,
                        "error": str(exc),
                    })
                    continue

        request_kind = defn.allowed_request_kinds[0]
        decision = can_request_source(source_name, request_kind, recent_count)

        planned.append({
            "source_name": source_name,
            "representative_request_kind": request_kind,
            "recent_request_count": recent_count,
            "rate_limit_per_minute": defn.default_rate_limit_per_minute,
            "governor_decision": decision.reason,
            "allowed": decision.allowed,
        })

    allowed_count = sum(1 for s in planned if s["allowed"])
    total = len(planned)

    return {
        "window_seconds": window_seconds,
        "planned_sources": planned,
        "total_sources": total,
        "allowed_count": allowed_count,
        "all_sources_allowed": allowed_count == total,
        "budget_summary": f"{allowed_count}/{total} sources allowed by Source Governor",
    }


def build_cycle_plan(validated_tokens: list[dict[str, Any]]) -> dict[str, Any]:
    """Build dry-run job plan for validated tokens. Does not enqueue jobs."""
    planned_jobs: list[dict[str, Any]] = []

    for token in validated_tokens:
        lane = token["lifecycle_lane"]
        if lane == "TRACK_FAST":
            planned_jobs.append({
                "job_kind": "TRACK_FAST_FIRST_15M",
                "token_mint": token["token_mint"],
                "lifecycle_lane": lane,
            })
        elif lane == "TRACK_NORMAL":
            planned_jobs.append({
                "job_kind": "TRACK_NORMAL_FIRST_15M",
                "token_mint": token["token_mint"],
                "lifecycle_lane": lane,
            })

    planned_jobs.append({
        "job_kind": "MEMORY_WINDOW_CLOSE",
        "token_mint": None,
        "lifecycle_lane": None,
    })

    return {
        "planned_jobs": planned_jobs,
        "planned_job_count": len(planned_jobs),
        "max_active_tokens": MAX_ACTIVE_TOKENS,
        "max_track_fast": MAX_TRACK_FAST,
        "max_track_normal": MAX_TRACK_NORMAL,
        "first_cycle_token_cap": MAX_TOKEN_COUNT,
        "zero_clean_memories_allowed": True,
        "clean_memory_forced": False,
        "paper_decisions_enabled": False,
    }


def determine_recommendation(
    token_validation: dict[str, Any],
    db_preflight: dict[str, Any],
    source_budget: dict[str, Any],
) -> tuple[str, list[str]]:
    """Compute BLOCKED or LIMITED_GO_FOR_OPERATOR_REVIEW with reasons. Pure function."""
    reasons: list[str] = []

    if not token_validation["valid"]:
        reasons.append(
            "token list validation failed: " + "; ".join(token_validation["errors"])
        )

    if not db_preflight["backup_confirmed"]:
        reasons.append("DB backup not confirmed")

    if not db_preflight["db_path_exists"]:
        reasons.append("DB path does not exist or was not provided")
    elif not db_preflight["preflight_passed"]:
        for err in db_preflight.get("errors", []):
            if "backup" not in err.lower():
                reasons.append(err)

    if not source_budget["all_sources_allowed"]:
        blocked = [
            s["source_name"] for s in source_budget["planned_sources"] if not s["allowed"]
        ]
        reasons.append(f"source budget blocked for: {', '.join(blocked)}")

    if reasons:
        return RECOMMENDATION_BLOCKED, reasons

    return RECOMMENDATION_LIMITED_GO, [
        "token list valid",
        "DB backup confirmed",
        "DB preflight passed (zero running jobs, zero active locks)",
        "source budget allows all planned sources",
        "still requires operator review before cycle execution",
    ]


def build_e2c_readiness_payload(
    tokens: list[dict[str, Any]],
    db_path: str | Path | None,
    *,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Build the full E2C active cycle readiness payload.

    No DB mutation. No source fetching. No paper decisions. No scheduler execution.
    """
    token_validation = validate_token_list(tokens)
    db_preflight = check_db_preflight(db_path, backup_confirmed=backup_confirmed)
    source_budget = plan_source_budget(db_path)
    cycle_plan = build_cycle_plan(token_validation.get("tokens", []))

    recommendation, recommendation_reasons = determine_recommendation(
        token_validation, db_preflight, source_budget
    )

    return {
        "command": "printer-plan-bounded-15m-memory-factory-cycle",
        "dry_run": True,
        "token_list_validation": token_validation,
        "db_preflight": db_preflight,
        "source_budget": source_budget,
        "cycle_plan": cycle_plan,
        "hard_locks": dict(HARD_LOCKS),
        "recommendation": recommendation,
        "recommendation_reasons": recommendation_reasons,
    }
