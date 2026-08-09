from __future__ import annotations

import json
from pathlib import Path
import subprocess

from printer_v1.operator_cli.holder_reliability_budget_control import build_operational_budget_preflight
from printer_v1.operator_cli.operational_memory_factory_command import (
    ADMISSION_OPERATION_CEILING,
    DISCOVERY_REQUEST_CEILING,
    GOVERNED_15M_REQUEST_CEILING,
    GOVERNED_REQUESTS_PER_TOKEN,
    _active_counts,
    _locked_capability_counts,
    _read_only,
    _validate_locked_baseline,
)
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import assert_migration_ledger_ready
from printer_v1.operator_cli.readiness_source_contract_preflight import build_readiness_source_contract_preflight
from printer_v1.operator_cli.unified_terminal_closure import assert_runtime_dependency_preflight
from printer_v1.operator_cli.window_15m_concrete_composition import (
    run_window_15m_concrete_composition_preflight,
    window_15m_preflight_builders,
)

REPO = Path.home() / "Developer" / "MoneyPrinter"
BRANCH = "agent/v2-9-8b-post-dtw95-window15m-rereadiness-audit"
HEAD = "80117db6b5888c44cab5ea68f592c945ffeb715c"
DB = REPO / "data" / "printer_v1.sqlite3"


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> int:
    phase = "START"
    try:
        phase = "GIT_CLEAN"
        if git("status", "--porcelain=v1", "-uno"):
            raise RuntimeError("tracked worktree/index is not clean")

        phase = "GIT_ALIGN"
        git("fetch", "origin", BRANCH)
        if git("rev-parse", "FETCH_HEAD") != HEAD:
            raise RuntimeError("remote rereadiness branch head drifted")
        local_exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{BRANCH}"],
            cwd=REPO,
        ).returncode == 0
        if local_exists:
            git("switch", BRANCH)
            if git("rev-parse", "HEAD") != HEAD:
                raise RuntimeError("local rereadiness branch head drifted")
        else:
            git("switch", "--track", "-c", BRANCH, f"origin/{BRANCH}")
        if git("branch", "--show-current") != BRANCH or git("rev-parse", "HEAD") != HEAD:
            raise RuntimeError("exact rereadiness Git identity mismatch")

        phase = "MIGRATION_LEDGER"
        migration = assert_migration_ledger_ready(
            mode="prepare", db_path=DB, migrations_dir=REPO / "migrations"
        )
        if migration.status != "PASS":
            raise RuntimeError(f"migration guard blocked: {migration.verdict}")

        phase = "NON_GIT_READINESS"
        source = build_readiness_source_contract_preflight()
        if source.get("status") != "READY" or int(source.get("external_requests") or 0) != 0:
            raise RuntimeError(f"source contract not zero-I/O READY: {source}")
        composition = run_window_15m_concrete_composition_preflight(
            repository_root=str(REPO), timeout_seconds=5.0
        )
        if composition.get("status") != "READY":
            raise RuntimeError(f"concrete composition not READY: {composition}")
        dependency = assert_runtime_dependency_preflight(
            repository_root=REPO,
            adapter_builders=window_15m_preflight_builders(timeout_seconds=5.0),
        )
        if dependency.status != "READY":
            raise RuntimeError(f"dependency preflight not READY: {dependency.to_dict()}")
        budget = build_operational_budget_preflight(
            admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
            discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
            governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
            governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
        )
        if budget.get("status") != "READY":
            raise RuntimeError(f"holder budget not READY: {budget}")

        phase = "AUTHORITATIVE_DB_READ_ONLY"
        conn = _read_only(DB)
        try:
            active = dict(_active_counts(conn))
            locked = dict(_locked_capability_counts(conn))
            historical_audit = int(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_paper_audit_reports WHERE paper_position_id IS NULL"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        if any(active.values()):
            raise RuntimeError(f"active operational residue: {active}")
        _validate_locked_baseline(locked)
        if historical_audit != 1:
            raise RuntimeError(f"historical paper-audit baseline changed: {historical_audit}")

        result = {
            "status": "PASS",
            "verdict": "V2_9_8B_POST_DTW95_WINDOW_15M_REREADINESS_PASS",
            "branch": BRANCH,
            "head": HEAD,
            "database": migration.database,
            "migration_guard": migration.verdict,
            "source_contract_status": source.get("status"),
            "source_contract_external_requests": int(source.get("external_requests") or 0),
            "concrete_composition_status": composition.get("status"),
            "dependency_status": dependency.status,
            "holder_budget_status": budget.get("status"),
            "active_counts": active,
            "historical_paper_audit_rows_preserved": historical_audit,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
            "authorization_created": False,
            "window_15m_started": False,
            "next_step": "REREADINESS_CLOSEOUT_BEFORE_ANY_FRESH_AUTHORIZATION",
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "verdict": "V2_9_8B_POST_DTW95_WINDOW_15M_REREADINESS_BLOCKED",
                    "phase": phase,
                    "error": f"{type(exc).__name__}:{exc}",
                    "source_calls": 0,
                    "scheduler_runtime_calls": 0,
                    "database_writes": 0,
                    "authorization_created": False,
                    "window_15m_started": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
