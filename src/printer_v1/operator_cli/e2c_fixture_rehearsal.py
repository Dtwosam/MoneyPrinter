"""E2C-E Fixture Rehearsal Package -- synthetic rehearsal of first bounded E2C cycle.

All functions are read-only with respect to the persistent database. No source
fetching. No scheduler runtime. No snapshot creation. No memory creation. No
retrieval activation. No paper decisions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2c_readiness import (
    HARD_LOCKS,
    RECOMMENDATION_LIMITED_GO,
    build_e2c_readiness_payload,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


RECOMMENDATION_FIXTURE_PASS: str = "FIXTURE_REHEARSAL_PASS"

# Tables that must exist after apply_migrations; checked unconditionally.
_REQUIRED_TABLES: tuple[str, ...] = (
    "printer_scheduler_jobs",
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
)

# Tables that may or may not exist; reported as "table_missing" when absent.
_OPTIONAL_TABLES: tuple[str, ...] = (
    "printer_token_snapshots",
    "printer_context_snapshots",
    "printer_contexts",
    "printer_memory_windows",
    "printer_memories",
    "printer_paper_decisions",
    "printer_paper_positions",
)


def _count_rows(db_path: Path, table: str) -> int | str:
    """Return row count for table, or 'table_missing' when the table does not exist."""
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return int(row[0])
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return "table_missing"
        raise


def _snapshot_counts(db_path: Path | None) -> dict[str, int | str]:
    """Collect row counts for all mutation-proof tables."""
    if db_path is None or not db_path.exists():
        return {}
    result: dict[str, int | str] = {}
    for table in _REQUIRED_TABLES + _OPTIONAL_TABLES:
        result[table] = _count_rows(db_path, table)
    return result


def _build_mutation_proof(
    counts_before: dict[str, int | str],
    counts_after: dict[str, int | str],
) -> dict[str, Any]:
    """Compare before/after row counts and produce mutation proof section."""
    if not counts_before:
        return {
            "tables_checked": {},
            "tables_missing": [],
            "counts_before": {},
            "counts_after": {},
            "changed_tables": [],
            "all_counts_unchanged": True,
            "note": "db_path not available or does not exist; no tables checked",
        }

    changed: list[str] = []
    tables_missing: list[str] = []

    for table, before in counts_before.items():
        after = counts_after.get(table, before)
        if before == "table_missing":
            tables_missing.append(table)
        elif before != after:
            changed.append(table)

    return {
        "tables_checked": {t: v for t, v in counts_before.items() if v != "table_missing"},
        "tables_missing": tables_missing,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "changed_tables": changed,
        "all_counts_unchanged": len(changed) == 0,
    }


def _build_fixture_evidence_plan(
    validated_tokens: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build fixture-only evidence plan for each planned token.

    Produces placeholder entries only. Does not fetch sources. Does not create
    snapshot, memory, context, or paper decision rows.
    """
    plan: list[dict[str, Any]] = []
    for token in validated_tokens:
        lane = token["lifecycle_lane"]
        job_kind = (
            "TRACK_FAST_FIRST_15M" if lane == "TRACK_FAST" else "TRACK_NORMAL_FIRST_15M"
        )
        evidence_placeholders = [
            {
                "source_name": src_name,
                "request_kind": defn.allowed_request_kinds[0],
                "status": "fixture_placeholder",
                "fixture_only": True,
            }
            for src_name, defn in SOURCE_REGISTRY.items()
            if not defn.requires_paid_plan
        ]
        plan.append({
            "token_mint": token["token_mint"],
            "lifecycle_lane": lane,
            "planned_job_kind": job_kind,
            "fixture_only": True,
            "source_fetching_enabled": False,
            "synthetic_evidence_only": True,
            "evidence_placeholders": evidence_placeholders,
            "snapshot_rows_created": 0,
            "memory_rows_created": 0,
            "context_rows_created": 0,
            "paper_decision_rows_created": 0,
        })
    return plan


def _determine_rehearsal_recommendation(
    e2c_readiness: dict[str, Any],
    mutation_proof: dict[str, Any],
) -> tuple[str, list[str]]:
    """Compute BLOCKED or FIXTURE_REHEARSAL_PASS with reasons. Pure function."""
    reasons: list[str] = []

    if e2c_readiness.get("recommendation") != RECOMMENDATION_LIMITED_GO:
        reasons.append(
            "e2c_readiness recommendation is "
            + repr(e2c_readiness.get("recommendation"))
            + "; must be LIMITED_GO_FOR_OPERATOR_REVIEW to pass fixture rehearsal"
        )
        for r in e2c_readiness.get("recommendation_reasons", []):
            reasons.append("  readiness gate: " + r)

    if not mutation_proof.get("all_counts_unchanged", True):
        changed = mutation_proof.get("changed_tables", [])
        reasons.append(
            "mutation proof failed: row counts changed in " + ", ".join(changed)
        )

    if reasons:
        return "BLOCKED", reasons

    return RECOMMENDATION_FIXTURE_PASS, [
        "e2c_readiness recommendation is LIMITED_GO_FOR_OPERATOR_REVIEW",
        "token list valid (1-2 tokens, valid mints, valid lifecycle lanes, no duplicates)",
        "DB backup confirmed",
        "DB preflight passed (zero running jobs, zero active locks)",
        "source budget allows all planned non-paid sources",
        "planned job shape valid"
        " (TRACK_FAST_FIRST_15M / TRACK_NORMAL_FIRST_15M / MEMORY_WINDOW_CLOSE)",
        "fixture evidence plan created (fixture_only: true, synthetic_evidence_only: true)",
        "mutation proof passed (row counts unchanged for all checked tables)",
        "all 11 hard-lock flags are False",
        "fixture rehearsal complete -- no cycle executed, no real sources fetched",
    ]


def build_e2c_fixture_rehearsal_payload(
    tokens: list[dict[str, Any]],
    db_path: str | Path | None,
    *,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Build the full E2C-E fixture rehearsal payload.

    No persistent DB mutation. No source fetching. No scheduler execution.
    No snapshot creation. No memory creation. No paper decisions.
    """
    resolved: Path | None = Path(db_path) if db_path is not None else None

    counts_before = _snapshot_counts(resolved)
    e2c_readiness = build_e2c_readiness_payload(
        tokens, db_path, backup_confirmed=backup_confirmed
    )
    counts_after = _snapshot_counts(resolved)

    mutation_proof = _build_mutation_proof(counts_before, counts_after)

    validated_tokens = (
        e2c_readiness.get("token_list_validation", {}).get("tokens", [])
    )
    fixture_evidence_plan = _build_fixture_evidence_plan(validated_tokens)

    recommendation, recommendation_reasons = _determine_rehearsal_recommendation(
        e2c_readiness, mutation_proof
    )

    return {
        "command": "printer-rehearse-bounded-15m-memory-factory-cycle",
        "dry_run": True,
        "fixture_only": True,
        "synthetic_evidence_only": True,
        "source_fetching_enabled": False,
        "e2c_readiness": e2c_readiness,
        "fixture_evidence_plan": fixture_evidence_plan,
        "mutation_proof": mutation_proof,
        "hard_locks": dict(HARD_LOCKS),
        "recommendation": recommendation,
        "recommendation_reasons": recommendation_reasons,
    }
