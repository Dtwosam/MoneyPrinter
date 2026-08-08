#!/usr/bin/env python3
"""Checkpoint 8 independent read-only inspection.

The inspector consumes only one frozen Checkpoint 8 proof directory. It never
starts Printer runtime work, never invokes report replay, and never mutates the
proof database. All database access is SQLite read-only/query-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from urllib.parse import quote

from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
)


_FROZEN_SUMMARY_NAME = "checkpoint8-controlling-proof-summary.json"
_INSPECTION_ARTIFACT_NAME = "checkpoint8-independent-inspection.json"
_PROTECTED_CAPABILITY_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)
_LONGER_WINDOWS = ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")


class Checkpoint8IndependentInspectionError(RuntimeError):
    """Fail-closed independent-inspection fault."""


def validate_independent_proof_db_target(
    db_path: str | Path,
    *,
    canonical_db_path: str | Path,
) -> Path:
    target = Path(db_path).expanduser().resolve()
    canonical = Path(canonical_db_path).expanduser().resolve()

    if target == canonical:
        raise Checkpoint8IndependentInspectionError(
            "CANONICAL_PRODUCTION_DB_FORBIDDEN"
        )
    if not target.is_file():
        raise Checkpoint8IndependentInspectionError(
            "INDEPENDENT_PROOF_DB_MISSING"
        )
    return target


def open_independent_read_only_db(
    db_path: str | Path,
    *,
    canonical_db_path: str | Path,
) -> sqlite3.Connection:
    target = validate_independent_proof_db_target(
        db_path,
        canonical_db_path=canonical_db_path,
    )
    uri = f"file:{quote(str(target))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _canonical_json_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_checkpoint8_frozen_summary(proof_dir: str | Path) -> dict[str, Any]:
    root = Path(proof_dir).expanduser().resolve()
    summary_path = root / _FROZEN_SUMMARY_NAME
    if not root.is_dir() or not summary_path.is_file():
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PROOF_SUMMARY_MISSING"
        )
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PROOF_SUMMARY_INVALID"
        ) from exc
    if not isinstance(payload, dict):
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PROOF_SUMMARY_INVALID"
        )
    observed = str(payload.get("frozen_evidence_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("frozen_evidence_sha256", None)
    expected = _canonical_json_sha256(unsigned)
    if observed != expected:
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_EVIDENCE_SHA256_MISMATCH"
        )
    return payload


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    if not _table_exists(connection, table):
        return ()
    return tuple(
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    )


def _rows_for_identity(
    connection: sqlite3.Connection,
    table: str,
    *,
    run_id: str,
    campaign_id: str,
) -> list[dict[str, Any]]:
    columns = _table_columns(connection, table)
    if not columns:
        return []
    predicates: list[str] = []
    params: list[str] = []
    if "run_id" in columns:
        predicates.append('CAST("run_id" AS TEXT)=?')
        params.append(run_id)
    if "campaign_run_id" in columns:
        predicates.append('CAST("campaign_run_id" AS TEXT)=?')
        params.append(run_id)
    if "campaign_id" in columns:
        predicates.append('CAST("campaign_id" AS TEXT)=?')
        params.append(campaign_id)
    if not predicates:
        return []
    sql = f'SELECT * FROM "{table}" WHERE ' + " OR ".join(predicates)
    return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]


def _all_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not _table_exists(connection, table):
        return []
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()]


def _json_objects_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for value in row.values():
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text[0] not in "{[":
            continue
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            objects.append(decoded)
        elif isinstance(decoded, list):
            objects.extend(item for item in decoded if isinstance(item, dict))
    return objects


def _deep_find(value: Any, names: Iterable[str]) -> Any:
    wanted = set(names)
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in wanted and child not in (None, ""):
                return child
        for child in value.values():
            found = _deep_find(child, wanted)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _deep_find(child, wanted)
            if found not in (None, ""):
                return found
    return None


def _row_or_json_value(row: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    for obj in _json_objects_from_row(row):
        found = _deep_find(obj, names)
        if found not in (None, ""):
            return found
    return None


def recompute_checkpoint8_database_safety(
    frozen_summary: dict[str, Any],
    *,
    canonical_db_path: str | Path,
) -> dict[str, Any]:
    pre = frozen_summary.get("pre_run_evidence")
    if not isinstance(pre, dict):
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PRE_RUN_EVIDENCE_MISSING"
        )
    db_text = str(pre.get("db_path") or "")
    if not db_text:
        raise Checkpoint8IndependentInspectionError("INDEPENDENT_PROOF_DB_MISSING")
    target = validate_independent_proof_db_target(
        db_text,
        canonical_db_path=canonical_db_path,
    )
    before = _sha256_file(target)
    connection = open_independent_read_only_db(
        target,
        canonical_db_path=canonical_db_path,
    )
    try:
        applied = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY rowid"
            ).fetchall()
        ]
        expected = list(canonical_migration_names())
        if applied != expected:
            raise Checkpoint8IndependentInspectionError(
                "CANONICAL_MIGRATION_LEDGER_MISMATCH"
            )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        fk_count = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    finally:
        connection.close()
    after = _sha256_file(target)
    if before != after:
        raise Checkpoint8IndependentInspectionError("READ_ONLY_DB_BYTES_CHANGED")
    return {
        "db_path": str(target),
        "db_sha256": after,
        "migration_count": len(applied),
        "migration_head": applied[-1] if applied else None,
        "canonical_migration_count": canonical_migration_count(),
        "integrity_check": integrity,
        "foreign_key_violations": fk_count,
        "read_only": True,
    }


def validate_checkpoint8_graph_projection(
    projection: dict[str, Any],
) -> dict[str, Any]:
    windows = projection.get("windows")
    if not isinstance(windows, list):
        raise Checkpoint8IndependentInspectionError(
            "EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED"
        )
    eligible = [
        row
        for row in windows
        if isinstance(row, dict)
        and row.get("window_kind") == "WINDOW_15M"
        and row.get("terminal") is True
    ]
    if len(eligible) != 2:
        raise Checkpoint8IndependentInspectionError(
            "EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED"
        )
    mints = [str(row.get("token_mint") or "") for row in eligible]
    if not all(mints) or len(set(mints)) != 2:
        raise Checkpoint8IndependentInspectionError(
            "EXACT_TWO_DISTINCT_MINTS_REQUIRED"
        )
    if any(row.get("memory_quality_label") != "CLEAN_MEMORY" for row in eligible):
        raise Checkpoint8IndependentInspectionError(
            "TWO_CLEAN_MEMORIES_REQUIRED"
        )
    fingerprints_present = all(
        row.get("fingerprint_present") is True
        or len(str(row.get("fingerprint_sha256") or "")) == 64
        for row in eligible
    )
    if not fingerprints_present:
        raise Checkpoint8IndependentInspectionError(
            "TWO_MEMORY_FINGERPRINTS_REQUIRED"
        )
    return {
        "exact_two_terminal_window_15m": True,
        "exact_two_distinct_mints": True,
        "both_clean_memory": True,
        "both_fingerprints_present": True,
        "token_mints": mints,
        "memory_window_ids": [row.get("memory_window_id") for row in eligible],
    }

def _normal_owner(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def validate_checkpoint8_governance_projection(
    projection: dict[str, Any],
) -> dict[str, Any]:
    if "source_accounting_exact" in projection:
        if projection.get("source_accounting_exact") is not True:
            raise Checkpoint8IndependentInspectionError(
                "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH"
            )
    else:
        source_owner = _normal_owner(projection.get("source_governor_owner"))
        if "sourcegovernor" not in source_owner:
            raise Checkpoint8IndependentInspectionError(
                "SOURCE_GOVERNOR_OWNER_MISMATCH"
            )

    if "scheduler_correspondence_exact" in projection:
        if projection.get("scheduler_correspondence_exact") is not True:
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
    else:
        scheduler_owner = _normal_owner(projection.get("central_scheduler_owner"))
        if "centralscheduler" not in scheduler_owner:
            raise Checkpoint8IndependentInspectionError(
                "CENTRAL_SCHEDULER_OWNER_MISMATCH"
            )

    counts = (
        int(projection.get("active_work_count") or 0),
        int(projection.get("locked_scheduler_job_count") or 0),
        int(projection.get("orphan_owned_work_count") or 0),
    )
    if any(counts):
        raise Checkpoint8IndependentInspectionError("ACTIVE_OR_ORPHAN_WORK_REMAINS")
    if (
        projection.get("lease_released") is not True
        or projection.get("lease_file_present") is True
    ):
        raise Checkpoint8IndependentInspectionError("LEASE_NOT_RELEASED")
    forbidden = (
        bool(projection.get("automatic_retry_created")),
        bool(projection.get("manual_rerun_allowed")),
        bool(projection.get("resume_allowed")),
        bool(projection.get("restart_created")),
        bool(projection.get("successor_created")),
    )
    if any(forbidden):
        raise Checkpoint8IndependentInspectionError("RETRY_OR_REUSE_FACT_FORBIDDEN")
    return {
        "source_governor_exact": True,
        "central_scheduler_exact": True,
        "zero_active_locked_orphan_work": True,
        "lease_released": True,
        "no_retry_rerun_resume_restart_successor": True,
    }

def validate_checkpoint8_frozen_safety(
    frozen_summary: dict[str, Any],
) -> dict[str, Any]:
    if frozen_summary.get("campaign_pass") is not True:
        raise Checkpoint8IndependentInspectionError("CAMPAIGN_PASS_REQUIRED")
    if frozen_summary.get("campaign_acceptance_verdict") != "CAMPAIGN_PASS":
        raise Checkpoint8IndependentInspectionError("ACCEPTANCE_PASS_REQUIRED")
    if int(frozen_summary.get("network_attempt_count") or 0) != 0:
        raise Checkpoint8IndependentInspectionError("NETWORK_ATTEMPTS_MUST_BE_ZERO")
    if int(frozen_summary.get("fixture_transport_operation_count") or 0) <= 0:
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_TRANSPORT_OPERATION_COUNT_REQUIRED"
        )
    if frozen_summary.get("replay_zero_work") is not True:
        raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_NOT_ZERO_WORK")
    replay = frozen_summary.get("report_only")
    if not isinstance(replay, dict):
        raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_MISSING")
    for key in (
        "source_calls",
        "scheduler_runtime_calls",
        "database_writes",
        "replay_new_source_calls",
        "replay_new_scheduler_calls",
        "replay_database_writes",
    ):
        if int(replay.get(key, 0) or 0) != 0:
            raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_NOT_ZERO_WORK")
    post = frozen_summary.get("post_run_evidence")
    if not isinstance(post, dict):
        raise Checkpoint8IndependentInspectionError("POST_RUN_EVIDENCE_MISSING")
    deltas = post.get("protected_capability_deltas")
    if not isinstance(deltas, dict) or any(int(value or 0) != 0 for value in deltas.values()):
        raise Checkpoint8IndependentInspectionError("PROTECTED_CAPABILITY_DELTA_NONZERO")
    longer = post.get("longer_window_counts")
    if not isinstance(longer, dict) or any(int(longer.get(label, 0) or 0) != 0 for label in _LONGER_WINDOWS):
        raise Checkpoint8IndependentInspectionError("LONGER_WINDOW_PRESENT")
    return {
        "campaign_pass": True,
        "acceptance_pass": True,
        "zero_network_attempts": True,
        "fixture_operations_positive": True,
        "replay_zero_work": True,
        "protected_capability_zero_delta": True,
        "longer_windows_absent": True,
    }


def _find_owner(rows: Iterable[dict[str, Any]], needle: str) -> str | None:
    wanted = "".join(ch for ch in needle.lower() if ch.isalnum())
    for row in rows:
        for value in row.values():
            normalized = _normal_owner(value)
            if wanted in normalized:
                return str(value)
    return None


def _row_is_active(row: dict[str, Any]) -> bool:
    terminal = {
        "complete",
        "completed",
        "succeeded",
        "success",
        "failed",
        "cancelled",
        "canceled",
        "released",
        "closed",
        "done",
    }
    for key in ("status", "state", "step_status", "run_status", "terminal_status"):
        if key in row and row[key] not in (None, ""):
            return str(row[key]).strip().lower() not in terminal
    return False


def _memory_window_ids(rows: Iterable[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        value = _row_or_json_value(row, ("memory_window_id", "window_id"))
        if value not in (None, ""):
            ids.add(str(value))
    return ids


def derive_checkpoint8_independent_db_projections(
    frozen_summary: dict[str, Any],
    *,
    canonical_db_path: str | Path,
) -> dict[str, Any]:
    """Reconstruct the exact current Checkpoint 8 graph from durable rows."""
    campaign_id = str(frozen_summary.get("campaign_id") or "").strip()
    campaign_run_id = str(frozen_summary.get("run_id") or "").strip()
    pre = frozen_summary.get("pre_run_evidence")
    if not campaign_id or not campaign_run_id or not isinstance(pre, dict):
        raise Checkpoint8IndependentInspectionError("CURRENT_RUN_IDENTITY_MISSING")
    db_path = str(pre.get("db_path") or "").strip()
    if not db_path:
        raise Checkpoint8IndependentInspectionError("INDEPENDENT_PROOF_DB_MISSING")

    def _rows(
        connection: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def _json_dict(value: Any, error: str) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise Checkpoint8IndependentInspectionError(error) from exc
        if not isinstance(parsed, dict):
            raise Checkpoint8IndependentInspectionError(error)
        return parsed

    def _text(value: Any) -> str:
        return str(value or "").strip()

    def _int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _canonical_set(records: Any, error: str) -> set[str]:
        if not isinstance(records, list) or not records:
            raise Checkpoint8IndependentInspectionError(error)
        encoded: list[str] = []
        for record in records:
            if not isinstance(record, dict):
                raise Checkpoint8IndependentInspectionError(error)
            encoded.append(
                json.dumps(
                    record,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        if len(encoded) != len(set(encoded)):
            raise Checkpoint8IndependentInspectionError(error)
        return set(encoded)

    connection = open_independent_read_only_db(
        db_path,
        canonical_db_path=canonical_db_path,
    )
    try:
        campaign_runs = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_runs "
            "WHERE campaign_id=? AND run_id=?",
            (campaign_id, campaign_run_id),
        )
        if not campaign_runs:
            raise Checkpoint8IndependentInspectionError("CURRENT_RUN_GRAPH_MISSING")
        if len(campaign_runs) != 1:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_FACTORY_RUN_BINDING_CARDINALITY_MISMATCH"
            )
        campaign_run = campaign_runs[0]
        factory_run_id = _text(campaign_run.get("authoritative_run_id"))
        if not factory_run_id:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_FACTORY_RUN_BINDING_MISSING"
            )
        factory_runs = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_runs WHERE run_id=?",
            (factory_run_id,),
        )
        if len(factory_runs) != 1:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_FACTORY_RUN_BINDING_MISSING"
            )

        replay = frozen_summary.get("report_only")
        replay = replay if isinstance(replay, dict) else {}
        replay_evidence = replay.get("full_run_terminal_evidence")
        replay_evidence = (
            replay_evidence if isinstance(replay_evidence, dict) else {}
        )
        replay_identity = replay_evidence.get("identity")
        replay_identity = replay_identity if isinstance(replay_identity, dict) else {}
        replay_factory = _text(replay_identity.get("factory_run_id"))
        if replay_factory and replay_factory != factory_run_id:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_FACTORY_RUN_IDENTITY_CONFLICT"
            )

        campaigns = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (campaign_id,),
        )
        if len(campaigns) != 1:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_CAMPAIGN_CARDINALITY_MISMATCH"
            )
        configurations = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_configurations "
            "WHERE campaign_id=?",
            (campaign_id,),
        )
        if len(configurations) != 1:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_CONFIGURATION_CARDINALITY_MISMATCH"
            )
        configuration_id = _text(configurations[0].get("configuration_id"))
        cycles = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_cycles "
            "WHERE campaign_id=? AND run_id=?",
            (campaign_id, campaign_run_id),
        )
        if len(cycles) != 1:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_CYCLE_CARDINALITY_MISMATCH"
            )
        cycle_id = _text(cycles[0].get("cycle_id"))
        slots = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
            "ORDER BY slot_ordinal, token_slot_id",
            (campaign_id, campaign_run_id, cycle_id),
        )
        campaign_windows = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_windows "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
            "ORDER BY window_id",
            (campaign_id, campaign_run_id, cycle_id),
        )
        supervision_rows = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_supervision "
            "WHERE campaign_id=? AND run_id=? AND configuration_id=?",
            (campaign_id, campaign_run_id, configuration_id),
        )
        if len(slots) != 2 or len(campaign_windows) != 2:
            raise Checkpoint8IndependentInspectionError(
                "EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED"
            )
        if len(supervision_rows) != 1:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_SUPERVISION_CARDINALITY_MISMATCH"
            )
        supervision = supervision_rows[0]
        if (
            _text(supervision.get("supervision_state")) != "TERMINAL"
            or _text(supervision.get("terminal_status")) != "COMPLETED"
            or not _text(supervision.get("cleanup_completed_at"))
            or not _text(supervision.get("lease_released_at"))
        ):
            raise Checkpoint8IndependentInspectionError(
                "SUPERVISION_TERMINAL_CLEANUP_MISMATCH"
            )
        supervision_id = _text(supervision.get("supervision_id"))

        slot_by_id = {_text(row.get("token_slot_id")): row for row in slots}
        if "" in slot_by_id or len(slot_by_id) != 2:
            raise Checkpoint8IndependentInspectionError(
                "EXACT_TWO_DISTINCT_MINTS_REQUIRED"
            )
        slot_mints = [_text(row.get("mint_identity")) for row in slots]
        slot_token_ids = [_text(row.get("token_row_id")) for row in slots]
        slot_pair_ids = [_text(row.get("pair_row_id")) for row in slots]
        if (
            not all(slot_mints)
            or len(set(slot_mints)) != 2
            or len(set(slot_token_ids)) != 2
            or len(set(slot_pair_ids)) != 2
        ):
            raise Checkpoint8IndependentInspectionError(
                "EXACT_TWO_DISTINCT_MINTS_REQUIRED"
            )

        windows: list[dict[str, Any]] = []
        campaign_window_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        for campaign_window in campaign_windows:
            if (
                _text(campaign_window.get("window_kind")) != "WINDOW_15M"
                or _int(campaign_window.get("support_only")) != 0
                or _text(campaign_window.get("window_state")) != "CLEAN_PROMOTED"
                or not _text(campaign_window.get("terminal_at"))
            ):
                raise Checkpoint8IndependentInspectionError(
                    "EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED"
                )
            slot_id = _text(campaign_window.get("token_slot_id"))
            slot = slot_by_id.get(slot_id)
            if slot is None:
                raise Checkpoint8IndependentInspectionError(
                    "CAMPAIGN_MEMORY_WINDOW_IDENTITY_MISMATCH"
                )
            if (
                _text(campaign_window.get("token_row_id"))
                != _text(slot.get("token_row_id"))
                or _text(campaign_window.get("pair_row_id"))
                != _text(slot.get("pair_row_id"))
            ):
                raise Checkpoint8IndependentInspectionError(
                    "CAMPAIGN_MEMORY_WINDOW_IDENTITY_MISMATCH"
                )
            memory_window_id = campaign_window.get("memory_window_row_id")
            if memory_window_id in (None, ""):
                raise Checkpoint8IndependentInspectionError(
                    "CAMPAIGN_MEMORY_WINDOW_BINDING_MISSING"
                )
            memory_rows = _rows(
                connection,
                "SELECT * FROM printer_memory_windows WHERE id=?",
                (memory_window_id,),
            )
            if len(memory_rows) != 1:
                raise Checkpoint8IndependentInspectionError(
                    "CAMPAIGN_MEMORY_WINDOW_BINDING_MISSING"
                )
            memory_window = memory_rows[0]
            expected_snapshots = _int(memory_window.get("expected_snapshot_count"))
            actual_snapshots = _int(memory_window.get("actual_snapshot_count"))
            coverage_state = _text(memory_window.get("coverage_state"))
            if (
                _text(memory_window.get("token_id"))
                != _text(slot.get("token_row_id"))
                or _text(memory_window.get("pair_id"))
                != _text(slot.get("pair_row_id"))
                or _text(memory_window.get("window_kind")) != "WINDOW_15M"
                or _text(memory_window.get("window_status")) != "WINDOW_CLOSED"
                or _text(memory_window.get("data_quality_label")) != "CLEAN_DATA"
                or _int(memory_window.get("do_not_train")) != 0
                or expected_snapshots <= 0
                or actual_snapshots != expected_snapshots
                or _int(memory_window.get("missing_snapshot_count")) != 0
                or coverage_state not in {"COMPLETE", "COVERAGE_PASS"}
            ):
                raise Checkpoint8IndependentInspectionError(
                    "CAMPAIGN_MEMORY_WINDOW_IDENTITY_MISMATCH"
                )

            episode_rows = _rows(
                connection,
                "SELECT * FROM printer_episodes WHERE memory_window_id=?",
                (memory_window_id,),
            )
            qualifying_episodes = [
                row
                for row in episode_rows
                if _text(row.get("episode_kind")) == "WINDOW_15M_CLEAN_MEMORY"
                and _text(row.get("episode_status")) == "COMPLETE"
                and _text(row.get("memory_status")) == "CLEAN_MEMORY"
                and _text(row.get("memory_quality_label")) == "CLEAN_MEMORY"
                and _text(row.get("data_quality_label")) == "CLEAN_DATA"
                and _int(row.get("do_not_train")) == 0
                and _text(row.get("token_id")) == _text(slot.get("token_row_id"))
                and _text(row.get("pair_id")) == _text(slot.get("pair_row_id"))
                and _text(row.get("window_kind")) == "WINDOW_15M"
            ]
            if len(qualifying_episodes) != 1:
                raise Checkpoint8IndependentInspectionError(
                    "CLEAN_EPISODE_CARDINALITY_MISMATCH"
                )
            episode = qualifying_episodes[0]
            episode_id = episode.get("id")
            fingerprint_rows = _rows(
                connection,
                "SELECT * FROM printer_memory_fingerprints WHERE episode_id=?",
                (episode_id,),
            )
            if len(fingerprint_rows) != 1:
                raise Checkpoint8IndependentInspectionError(
                    "FINGERPRINT_CARDINALITY_MISMATCH"
                )
            fingerprint = fingerprint_rows[0]
            if (
                _text(fingerprint.get("fingerprint_kind"))
                != "STATIC_CONDITION_SUMMARY"
                or _text(fingerprint.get("memory_status")) != "CLEAN_MEMORY"
                or _text(fingerprint.get("data_quality_label")) != "CLEAN_DATA"
                or _int(fingerprint.get("do_not_train")) != 0
            ):
                raise Checkpoint8IndependentInspectionError(
                    "FINGERPRINT_PAYLOAD_IDENTITY_MISMATCH"
                )
            payload = _json_dict(
                fingerprint.get("fingerprint_payload_json"),
                "FINGERPRINT_PAYLOAD_IDENTITY_MISMATCH",
            )
            if (
                _text(payload.get("episode_id")) != _text(episode_id)
                or _text(payload.get("window_id")) != _text(memory_window_id)
                or _text(payload.get("token_id")) != _text(slot.get("token_row_id"))
                or _text(payload.get("pair_id")) != _text(slot.get("pair_row_id"))
                or _text(payload.get("window_kind")) != "WINDOW_15M"
            ):
                raise Checkpoint8IndependentInspectionError(
                    "FINGERPRINT_PAYLOAD_IDENTITY_MISMATCH"
                )

            pair_key = (
                _text(slot.get("token_row_id")),
                _text(slot.get("pair_row_id")),
            )
            campaign_window_by_pair[pair_key] = campaign_window
            windows.append(
                {
                    "campaign_window_id": _text(campaign_window.get("window_id")),
                    "token_mint": _text(slot.get("mint_identity")),
                    "token_id": slot.get("token_row_id"),
                    "pair_id": slot.get("pair_row_id"),
                    "memory_window_id": memory_window_id,
                    "window_kind": "WINDOW_15M",
                    "terminal": True,
                    "memory_quality_label": "CLEAN_MEMORY",
                    "fingerprint_present": True,
                    "episode_id": episode_id,
                }
            )

        if len(campaign_window_by_pair) != 2:
            raise Checkpoint8IndependentInspectionError(
                "CAMPAIGN_MEMORY_WINDOW_IDENTITY_MISMATCH"
            )

        run_steps = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_run_steps "
            "WHERE run_id=? ORDER BY id, step_key",
            (factory_run_id,),
        )
        if len(run_steps) != 18:
            raise Checkpoint8IndependentInspectionError(
                "FACTORY_RUN_STEP_CORROBORATION_MISMATCH"
            )
        run_step_job_ids: set[int] = set()
        step_counts: dict[tuple[str, str], dict[str, int]] = {
            key: {"SNAPSHOT": 0, "WINDOW_CLOSE": 0}
            for key in campaign_window_by_pair
        }
        for step in run_steps:
            pair_key = (_text(step.get("token_id")), _text(step.get("pair_id")))
            if pair_key not in campaign_window_by_pair:
                raise Checkpoint8IndependentInspectionError(
                    "FACTORY_RUN_STEP_CORROBORATION_MISMATCH"
                )
            step_kind = _text(step.get("step_kind"))
            if step_kind not in {"SNAPSHOT", "WINDOW_CLOSE"}:
                raise Checkpoint8IndependentInspectionError(
                    "FACTORY_RUN_STEP_CORROBORATION_MISMATCH"
                )
            if _text(step.get("step_status")) not in {
                "SUCCEEDED",
                "SUCCESS",
                "COMPLETED",
            }:
                raise Checkpoint8IndependentInspectionError(
                    "FACTORY_RUN_STEP_CORROBORATION_MISMATCH"
                )
            scheduler_job_id = step.get("scheduler_job_id")
            if scheduler_job_id in (None, ""):
                raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
            run_step_job_ids.add(_int(scheduler_job_id))
            step_counts[pair_key][step_kind] += 1
            if step_kind == "WINDOW_CLOSE":
                expected_window_id = campaign_window_by_pair[pair_key].get(
                    "memory_window_row_id"
                )
                if _text(step.get("memory_window_id")) != _text(expected_window_id):
                    raise Checkpoint8IndependentInspectionError(
                        "FACTORY_RUN_STEP_CORROBORATION_MISMATCH"
                    )
        if len(run_step_job_ids) != 18 or any(
            counts != {"SNAPSHOT": 8, "WINDOW_CLOSE": 1}
            for counts in step_counts.values()
        ):
            raise Checkpoint8IndependentInspectionError(
                "FACTORY_RUN_STEP_CORROBORATION_MISMATCH"
            )

        campaign_scheduler_work = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
            "ORDER BY scheduler_work_id",
            (campaign_id, campaign_run_id, cycle_id),
        )
        if len(campaign_scheduler_work) != 28:
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        scheduler_job_ids = [_int(row.get("scheduler_job_id")) for row in campaign_scheduler_work]
        if (
            any(value <= 0 for value in scheduler_job_ids)
            or len(set(scheduler_job_ids)) != 28
        ):
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        placeholders = ",".join("?" for _ in scheduler_job_ids)
        scheduler_jobs = _rows(
            connection,
            f"SELECT * FROM printer_scheduler_jobs WHERE id IN ({placeholders})",
            tuple(scheduler_job_ids),
        )
        job_by_id = {_int(row.get("id")): row for row in scheduler_jobs}
        if set(job_by_id) != set(scheduler_job_ids):
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        terminal_job_states = {
            "SUCCEEDED",
            "COMPLETED",
            "FAILED",
            "SKIPPED",
            "CANCELLED",
            "CANCELED",
        }
        if any(
            _text(row.get("status")) not in terminal_job_states
            or _text(row.get("locked_at"))
            or _text(row.get("lock_owner"))
            for row in scheduler_jobs
        ):
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        if any(
            _text(row.get("ownership_contract_version")) != "V2_STAGE_SCOPED"
            for row in campaign_scheduler_work
        ):
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")

        lifecycle_work = [
            row
            for row in campaign_scheduler_work
            if _text(row.get("work_scope")) == "WINDOW_LIFECYCLE"
        ]
        discovery_scheduler_work = [
            row
            for row in campaign_scheduler_work
            if _text(row.get("work_scope")) == "DISCOVERY_SELECTION"
        ]
        handoff_work = [
            row
            for row in campaign_scheduler_work
            if _text(row.get("work_scope")) == "FIRST_15M_HANDOFF"
        ]
        if (
            len(lifecycle_work) != 18
            or len(discovery_scheduler_work) != 8
            or len(handoff_work) != 2
        ):
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        for row in lifecycle_work:
            if _text(row.get("factory_run_id")) != factory_run_id:
                raise Checkpoint8IndependentInspectionError(
                    "LIFECYCLE_FACTORY_RUN_IDENTITY_MISMATCH"
                )
            if _text(row.get("work_state")) != "SUCCEEDED":
                raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        lifecycle_job_ids = {_int(row.get("scheduler_job_id")) for row in lifecycle_work}
        if lifecycle_job_ids != run_step_job_ids:
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")

        discovery_work = _rows(
            connection,
            "SELECT * FROM printer_discovery_work "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
            "ORDER BY discovery_work_id",
            (campaign_id, campaign_run_id, cycle_id),
        )
        if len(discovery_work) != 8:
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")
        discovery_job_ids = {_int(row.get("scheduler_job_id")) for row in discovery_work}
        scheduler_discovery_job_ids = {
            _int(row.get("scheduler_job_id")) for row in discovery_scheduler_work
        }
        if discovery_job_ids != scheduler_discovery_job_ids or any(
            _text(row.get("work_state")) != "SUCCEEDED" for row in discovery_work
        ):
            raise Checkpoint8IndependentInspectionError("SCHEDULER_JOIN_MISMATCH")

        source_requests = {
            _int(row.get("id")): row
            for row in _all_rows(connection, "printer_source_requests")
        }
        source_responses = {
            _int(row.get("id")): row
            for row in _all_rows(connection, "printer_source_responses")
        }

        def _validate_request_response(request_id: Any, response_id: Any) -> None:
            if request_id in (None, "") and response_id in (None, ""):
                return
            if request_id in (None, "") or response_id in (None, ""):
                raise Checkpoint8IndependentInspectionError(
                    "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
                )
            request = source_requests.get(_int(request_id))
            response = source_responses.get(_int(response_id))
            if request is None or response is None:
                raise Checkpoint8IndependentInspectionError(
                    "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
                )
            if (
                _int(response.get("source_request_id")) != _int(request_id)
                or _text(response.get("source_name")) != _text(request.get("source_name"))
            ):
                raise Checkpoint8IndependentInspectionError(
                    "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
                )

        validated_source_links = 0
        for row in lifecycle_work:
            request_id = row.get("source_request_id")
            response_id = row.get("source_response_id")
            failure_id = row.get("source_failure_id")
            if failure_id not in (None, ""):
                raise Checkpoint8IndependentInspectionError(
                    "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
                )
            if request_id not in (None, "") or response_id not in (None, ""):
                _validate_request_response(request_id, response_id)
                validated_source_links += 1

        discovery_ids = [_text(row.get("discovery_work_id")) for row in discovery_work]
        placeholders = ",".join("?" for _ in discovery_ids)
        discovery_links = _rows(
            connection,
            "SELECT * FROM printer_discovery_work_source_links "
            f"WHERE discovery_work_id IN ({placeholders}) "
            "ORDER BY discovery_work_id, link_ordinal",
            tuple(discovery_ids),
        )
        for row in discovery_links:
            failure_id = row.get("source_failure_id")
            if failure_id not in (None, ""):
                failure_rows = _rows(
                    connection,
                    "SELECT * FROM printer_source_failures WHERE id=?",
                    (failure_id,),
                )
                if len(failure_rows) != 1:
                    raise Checkpoint8IndependentInspectionError(
                        "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
                    )
                failure_request_id = failure_rows[0].get("source_request_id")
                if (
                    row.get("source_request_id") not in (None, "")
                    and _int(failure_request_id) != _int(row.get("source_request_id"))
                ):
                    raise Checkpoint8IndependentInspectionError(
                        "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
                    )
                validated_source_links += 1
                continue
            _validate_request_response(
                row.get("source_request_id"),
                row.get("source_response_id"),
            )
            validated_source_links += 1
        if validated_source_links <= 0:
            raise Checkpoint8IndependentInspectionError(
                "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH"
            )

        report_rows = _rows(
            connection,
            "SELECT * FROM printer_memory_factory_campaign_reports "
            "WHERE campaign_id=? AND configuration_id=? "
            "AND report_kind='TERMINAL' AND report_state='REPORT_TERMINAL'",
            (campaign_id, configuration_id),
        )
        if len(report_rows) != 1:
            raise Checkpoint8IndependentInspectionError(
                "TERMINAL_REPORT_CARDINALITY_MISMATCH"
            )
        report_row = report_rows[0]
        report_json = str(report_row.get("report_json") or "")
        report_hash = _text(report_row.get("report_hash"))
        if (
            not report_json
            or hashlib.sha256(report_json.encode("utf-8")).hexdigest() != report_hash
        ):
            raise Checkpoint8IndependentInspectionError("REPORT_HASH_MISMATCH")
        report_payload = _json_dict(report_json, "REPORT_HASH_MISMATCH")
        report_evidence = report_payload.get("full_run_terminal_evidence")
        report_evidence = (
            report_evidence if isinstance(report_evidence, dict) else report_payload
        )
        report_identity = report_evidence.get("identity")
        report_identity = report_identity if isinstance(report_identity, dict) else {}
        outer_report_identity = report_payload.get("identity")
        outer_report_identity = (
            outer_report_identity if isinstance(outer_report_identity, dict) else {}
        )

        expected_identity = {
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "configuration_id": configuration_id,
            "cycle_id": cycle_id,
            "factory_run_id": factory_run_id,
            "supervision_id": supervision_id,
        }
        for key, expected in expected_identity.items():
            aliases = (key, "run_id") if key == "campaign_run_id" else (key,)
            values = [
                _text(identity.get(alias))
                for identity in (report_identity, outer_report_identity)
                for alias in aliases
                if identity.get(alias) not in (None, "")
            ]
            if values and any(value != expected for value in values):
                raise Checkpoint8IndependentInspectionError(
                    "TERMINAL_REPORT_IDENTITY_MISMATCH"
                )

        execution_id = _text(report_identity.get("execution_id")) or _text(
            outer_report_identity.get("execution_id")
        ) or _text(replay_identity.get("execution_id"))
        if not execution_id:
            raise Checkpoint8IndependentInspectionError(
                "TERMINAL_REPORT_IDENTITY_MISMATCH"
            )

        artifact_root_text = _text(pre.get("artifact_root"))
        artifact_root = (
            Path(artifact_root_text).expanduser().resolve()
            if artifact_root_text
            else Path(db_path).expanduser().resolve().parent / "checkpoint8-artifacts"
        )
        if not artifact_root.is_dir():
            raise Checkpoint8IndependentInspectionError(
                "REPORT_ARTIFACT_HASH_MISMATCH"
            )
        execution_root = artifact_root / execution_id
        search_root = execution_root if execution_root.is_dir() else artifact_root
        report_artifacts = sorted(search_root.rglob("*.campaign-report.json"))
        if len(report_artifacts) != 1:
            raise Checkpoint8IndependentInspectionError(
                "REPORT_ARTIFACT_HASH_MISMATCH"
            )
        report_bytes = report_json.encode("utf-8")
        artifact_bytes = report_artifacts[0].read_bytes()
        if (
            artifact_bytes != report_bytes
            or hashlib.sha256(artifact_bytes).hexdigest() != report_hash
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_ARTIFACT_HASH_MISMATCH"
            )

        accounting = report_evidence.get("full_run_accounting")
        accounting = accounting if isinstance(accounting, dict) else {}
        owner_evidence = accounting.get("owner_evidence")
        owner_evidence = owner_evidence if isinstance(owner_evidence, dict) else {}
        action_evidence = accounting.get("action_local_evidence")
        action_evidence = action_evidence if isinstance(action_evidence, dict) else {}
        owner_transports = owner_evidence.get("transport_operations")
        action_transports = action_evidence.get("transport_identities")
        if not isinstance(action_transports, list):
            action_transports = action_evidence.get("transport_operations")
        owner_transport_set = _canonical_set(
            owner_transports,
            "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH",
        )
        action_transport_set = _canonical_set(
            action_transports,
            "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH",
        )
        if owner_transport_set != action_transport_set:
            raise Checkpoint8IndependentInspectionError(
                "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH"
            )
        for record in owner_transports:
            stage = _text(record.get("stage_id")) or _text(record.get("stage"))
            ordinal = record.get("ordinal")
            if ordinal in (None, ""):
                ordinal = record.get("within_request_ordinal")
            if ordinal in (None, ""):
                ordinal = record.get("operation_ordinal")
            if (
                not _text(record.get("governed_request_kind"))
                or not _text(record.get("source_name"))
                or not stage
                or not _text(record.get("target_category"))
                or not _text(record.get("target_identity"))
                or ordinal in (None, "")
                or not _text(record.get("result"))
            ):
                raise Checkpoint8IndependentInspectionError(
                    "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH"
                )

        for key in (
            "scheduler_work_identities",
            "local_validation_identities",
            "lifecycle_reservation_identities",
        ):
            owner_records = owner_evidence.get(key)
            if not isinstance(owner_records, list):
                owner_records = accounting.get(key)
            owner_set = _canonical_set(
                owner_records,
                "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH",
            )
            action_records = action_evidence.get(key)
            if isinstance(action_records, list) and action_records:
                action_set = _canonical_set(
                    action_records,
                    "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH",
                )
                if owner_set != action_set:
                    raise Checkpoint8IndependentInspectionError(
                        "SOURCE_GOVERNOR_ACCOUNTING_MISMATCH"
                    )

        authorization = report_evidence.get("authorization_and_invocation")
        authorization = authorization if isinstance(authorization, dict) else {}
        proof_expectation = authorization.get("proof_expectation")
        proof_expectation = (
            proof_expectation if isinstance(proof_expectation, dict) else {}
        )
        expectation_factory = _text(proof_expectation.get("factory_run_id"))
        if expectation_factory and expectation_factory != factory_run_id:
            raise Checkpoint8IndependentInspectionError(
                "CURRENT_FACTORY_RUN_IDENTITY_CONFLICT"
            )

        terminal = frozen_summary.get("terminal")
        terminal = terminal if isinstance(terminal, dict) else {}
        lease_path = _text(supervision.get("lease_lock_path"))
        active_work_count = sum(
            1
            for row in [*campaign_scheduler_work, *discovery_work]
            if _text(row.get("work_state"))
            not in {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED", "CANCELED"}
        )
        locked_scheduler_job_count = sum(
            1
            for row in scheduler_jobs
            if _text(row.get("locked_at")) or _text(row.get("lock_owner"))
        )
        governance = {
            "source_accounting_exact": True,
            "scheduler_correspondence_exact": True,
            "active_work_count": active_work_count,
            "locked_scheduler_job_count": locked_scheduler_job_count,
            "orphan_owned_work_count": 0,
            "lease_released": bool(_text(supervision.get("lease_released_at"))),
            "lease_file_present": bool(lease_path and Path(lease_path).exists()),
            "automatic_retry_created": bool(
                frozen_summary.get("automatic_retry_created", False)
            ),
            "manual_rerun_allowed": bool(
                proof_expectation.get("manual_rerun_allowed", False)
            ),
            "resume_allowed": bool(proof_expectation.get("resume_allowed", False)),
            "restart_created": bool(
                terminal.get("restart_created", report_payload.get("restart_created", False))
            ) or bool(proof_expectation.get("restart_allowed", False)),
            "successor_created": bool(
                terminal.get("successor_created", report_payload.get("successor_created", False))
            ) or bool(proof_expectation.get("successor_allowed", False)),
        }
    finally:
        connection.close()

    return {
        "identity": {
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "configuration_id": configuration_id,
            "cycle_id": cycle_id,
            "factory_run_id": factory_run_id,
            "supervision_id": supervision_id,
            "execution_id": execution_id,
            "report_hash": report_hash,
        },
        "graph": {
            "campaign_id": campaign_id,
            "run_id": campaign_run_id,
            "factory_run_id": factory_run_id,
            "configuration_id": configuration_id,
            "cycle_id": cycle_id,
            "windows": windows,
        },
        "governance": governance,
    }

def validate_checkpoint8_report_and_manifest_identity(
    frozen_summary: dict[str, Any],
    *,
    reconstructed_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    campaign_id = str(frozen_summary.get("campaign_id") or "").strip()
    campaign_run_id = str(frozen_summary.get("run_id") or "").strip()
    terminal = frozen_summary.get("terminal")
    replay = frozen_summary.get("report_only")
    pre = frozen_summary.get("pre_run_evidence")
    if (
        not campaign_id
        or not campaign_run_id
        or not isinstance(terminal, dict)
        or not isinstance(replay, dict)
        or not isinstance(pre, dict)
    ):
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_IDENTITY_MISMATCH"
        )

    terminal_campaign = str(terminal.get("campaign_id") or "").strip()
    terminal_run = str(terminal.get("run_id") or "").strip()
    if terminal_campaign and terminal_campaign != campaign_id:
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_IDENTITY_MISMATCH"
        )
    if terminal_run and terminal_run != campaign_run_id:
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_IDENTITY_MISMATCH"
        )

    terminal_report = terminal.get("report")
    terminal_report = terminal_report if isinstance(terminal_report, dict) else {}
    package_campaign = str(terminal_report.get("campaign_id") or "").strip()
    package_run = str(terminal_report.get("run_id") or "").strip()
    if package_campaign and package_campaign != campaign_id:
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_IDENTITY_MISMATCH"
        )
    if package_run and package_run != campaign_run_id:
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_IDENTITY_MISMATCH"
        )

    requested_identity = replay.get("requested_identity")
    if isinstance(requested_identity, dict):
        if replay.get("status") != "REPLAYED" or replay.get("mode") != "REPORT_ONLY":
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
        if (
            str(requested_identity.get("campaign_id") or "").strip() != campaign_id
            or str(requested_identity.get("run_id") or "").strip()
            != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
    else:
        if (
            str(replay.get("campaign_id") or "").strip() != campaign_id
            or str(replay.get("run_id") or "").strip() != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )

    replay_evidence = replay.get("full_run_terminal_evidence")
    replay_evidence = replay_evidence if isinstance(replay_evidence, dict) else {}
    replay_identity = replay_evidence.get("identity")
    replay_identity = replay_identity if isinstance(replay_identity, dict) else {}
    if replay_identity:
        if (
            str(replay_identity.get("campaign_id") or "").strip() != campaign_id
            or str(replay_identity.get("campaign_run_id") or "").strip()
            != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )

    if reconstructed_identity:
        for key in (
            "configuration_id",
            "cycle_id",
            "factory_run_id",
            "supervision_id",
            "execution_id",
        ):
            expected = str(reconstructed_identity.get(key) or "").strip()
            observed = str(replay_identity.get(key) or "").strip()
            if expected and observed and observed != expected:
                raise Checkpoint8IndependentInspectionError(
                    "REPORT_REPLAY_IDENTITY_MISMATCH"
                )

    manifest = str(
        frozen_summary.get("fixture_composition_manifest_sha256") or ""
    ).strip()
    if len(manifest) != 64:
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
    manifest_values = [manifest]
    pre_manifest = str(pre.get("fixture_composition_manifest_sha256") or "").strip()
    if pre_manifest:
        manifest_values.append(pre_manifest)
    replay_manifest = str(
        replay.get("fixture_composition_manifest_sha256") or ""
    ).strip()
    if replay_manifest:
        manifest_values.append(replay_manifest)
    authorization = replay_evidence.get("authorization_and_invocation")
    authorization = authorization if isinstance(authorization, dict) else {}
    proof_expectation = authorization.get("proof_expectation")
    proof_expectation = (
        proof_expectation if isinstance(proof_expectation, dict) else {}
    )
    expectation_manifest = str(
        proof_expectation.get("fixture_composition_manifest_sha256") or ""
    ).strip()
    if expectation_manifest:
        manifest_values.append(expectation_manifest)
    if any(value != manifest for value in manifest_values):
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
    proof_id = str(frozen_summary.get("proof_id") or "").strip()
    expectation_proof_id = str(proof_expectation.get("proof_id") or "").strip()
    if expectation_proof_id and expectation_proof_id != proof_id:
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
    return {
        "campaign_identity_exact": True,
        "run_identity_exact": True,
        "fixture_manifest_exact": True,
    }

def build_checkpoint8_independent_findings(
    *,
    frozen_summary: dict[str, Any],
    database_safety: dict[str, Any],
    graph_projection: dict[str, Any],
    governance_projection: dict[str, Any],
    frozen_safety: dict[str, Any],
    report_and_manifest_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db_ok = (
        database_safety.get("migration_count") == canonical_migration_count()
        and database_safety.get("migration_head") == canonical_migration_names()[-1]
        and database_safety.get("integrity_check") == "ok"
        and int(database_safety.get("foreign_key_violations") or 0) == 0
        and database_safety.get("read_only") is True
    )
    graph_ok = all(
        graph_projection.get(key) is True
        for key in (
            "exact_two_terminal_window_15m",
            "exact_two_distinct_mints",
            "both_clean_memory",
            "both_fingerprints_present",
        )
    )
    governance_ok = all(
        governance_projection.get(key) is True
        for key in (
            "source_governor_exact",
            "central_scheduler_exact",
            "zero_active_locked_orphan_work",
            "lease_released",
            "no_retry_rerun_resume_restart_successor",
        )
    )
    safety_ok = all(bool(value) for value in frozen_safety.values())
    identity_ok = True if report_and_manifest_identity is None else all(
        report_and_manifest_identity.get(key) is True
        for key in (
            "campaign_identity_exact",
            "run_identity_exact",
            "fixture_manifest_exact",
        )
    )
    if not all((db_ok, graph_ok, governance_ok, safety_ok, identity_ok)):
        raise Checkpoint8IndependentInspectionError("INDEPENDENT_FINDINGS_NOT_PASS")
    return {
        "verdict": "CHECKPOINT8_INDEPENDENT_INSPECTION_PASS",
        "pass": True,
        "proof_id": frozen_summary.get("proof_id"),
        "campaign_id": frozen_summary.get("campaign_id"),
        "run_id": frozen_summary.get("run_id"),
        "frozen_evidence_sha256": frozen_summary.get("frozen_evidence_sha256"),
        "database_safety": database_safety,
        "graph_projection": graph_projection,
        "governance_projection": governance_projection,
        "frozen_safety": frozen_safety,
        "report_and_manifest_identity": report_and_manifest_identity,
    }


def write_checkpoint8_independent_inspection_artifact(
    proof_dir: str | Path,
    findings: dict[str, Any],
) -> Path:
    root = Path(proof_dir).expanduser().resolve()
    if not root.is_dir():
        raise Checkpoint8IndependentInspectionError("FROZEN_PROOF_DIRECTORY_MISSING")
    artifact = root / _INSPECTION_ARTIFACT_NAME
    try:
        with artifact.open("x", encoding="utf-8") as handle:
            json.dump(findings, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
    except FileExistsError as exc:
        raise Checkpoint8IndependentInspectionError(
            "INDEPENDENT_INSPECTION_ARTIFACT_ALREADY_EXISTS"
        ) from exc
    return artifact


def inspect_checkpoint8_frozen_proof_directory(
    proof_dir: str | Path,
) -> dict[str, Any]:
    frozen_summary = load_checkpoint8_frozen_summary(proof_dir)
    database_safety = recompute_checkpoint8_database_safety(
        frozen_summary,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    projections = derive_checkpoint8_independent_db_projections(
        frozen_summary,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    graph_projection = validate_checkpoint8_graph_projection(projections["graph"])
    governance_projection = validate_checkpoint8_governance_projection(
        projections["governance"]
    )
    frozen_safety = validate_checkpoint8_frozen_safety(frozen_summary)
    report_identity = validate_checkpoint8_report_and_manifest_identity(
        frozen_summary,
        reconstructed_identity=projections.get("identity"),
    )
    findings = build_checkpoint8_independent_findings(
        frozen_summary=frozen_summary,
        database_safety=database_safety,
        graph_projection=graph_projection,
        governance_projection=governance_projection,
        frozen_safety=frozen_safety,
        report_and_manifest_identity=report_identity,
    )
    artifact = write_checkpoint8_independent_inspection_artifact(
        proof_dir,
        findings,
    )
    result = dict(findings)
    result["inspection_artifact"] = str(artifact)
    return result

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent read-only inspection of one frozen Checkpoint 8 proof directory"
    )
    parser.add_argument("--proof-dir", required=True)
    args = parser.parse_args(argv)
    result = inspect_checkpoint8_frozen_proof_directory(args.proof_dir)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
