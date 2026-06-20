"""Read-only operator database status helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.operator_db.paths import resolve_operator_db_path


STATE_NO_DB = "NO_PERSISTENT_DB_FOUND"
STATE_SCHEMA_ONLY = "PERSISTENT_DB_EMPTY_SCHEMA_ONLY"
STATE_SOURCE_ONLY_SMOKE_CHECK = "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK"
STATE_TEST_ONLY = "PERSISTENT_DB_HAS_TEST_ONLY_ROWS"
STATE_TOKEN_ROWS = "PERSISTENT_DB_HAS_REAL_TOKEN_ROWS"
STATE_MEMORY_ROWS = "PERSISTENT_DB_HAS_REAL_MEMORY_ROWS"
STATE_PAPER_ROWS = "PERSISTENT_DB_HAS_REAL_PAPER_ROWS"
STATE_UNCLEAR = "PERSISTENT_DB_STATE_UNCLEAR"

STATE_CLASSIFICATIONS = {
    STATE_NO_DB,
    STATE_SCHEMA_ONLY,
    STATE_SOURCE_ONLY_SMOKE_CHECK,
    STATE_TEST_ONLY,
    STATE_TOKEN_ROWS,
    STATE_MEMORY_ROWS,
    STATE_PAPER_ROWS,
    STATE_UNCLEAR,
}

CORE_TABLES = [
    "printer_schema_migrations",
    "printer_tokens",
    "printer_pairs",
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_tracking_queue",
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_operator_review_reports",
    "printer_operator_review_items",
    "printer_validation_runs",
    "printer_validation_items",
]

SOURCE_TABLES = [
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
]

MEMORY_TABLES = [
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
]

PAPER_TABLES = [
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]

SNAPSHOT_TABLES = [
    "printer_token_snapshots",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
]

SOURCE_ONLY_BLOCKER_TABLES = [
    "printer_tokens",
    "printer_pairs",
    "printer_tracking_queue",
    "printer_scheduler_jobs",
    *SNAPSHOT_TABLES,
    *MEMORY_TABLES,
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    *PAPER_TABLES,
]


@contextmanager
def connect_read_only(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    resolved = Path(db_path).resolve(strict=True)
    uri = resolved.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_count(connection: sqlite3.Connection, table_name: str) -> int | None:
    if not table_exists(connection, table_name):
        return None
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def get_core_table_counts(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, int | None]:
    resolved = resolve_operator_db_path(db_path, project_root)
    if not resolved.is_file():
        return {table: None for table in CORE_TABLES}
    with connect_read_only(resolved) as connection:
        return {table: table_count(connection, table) for table in CORE_TABLES}


def get_schema_migration_status(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_operator_db_path(db_path, project_root)
    if not resolved.is_file():
        return {"db_path": str(resolved), "exists": False, "applied_migrations": [], "latest_migration": None}
    with connect_read_only(resolved) as connection:
        if not table_exists(connection, "printer_schema_migrations"):
            return {"db_path": str(resolved), "exists": True, "applied_migrations": [], "latest_migration": None}
        rows = connection.execute("SELECT version FROM printer_schema_migrations ORDER BY version ASC").fetchall()
    versions = [row["version"] for row in rows]
    return {
        "db_path": str(resolved),
        "exists": True,
        "applied_migrations": versions,
        "latest_migration": versions[-1] if versions else None,
    }


def row_count_sum(counts: dict[str, int | None], tables: list[str]) -> int:
    return sum(counts.get(table) or 0 for table in tables)


def only_schema_rows_exist(counts: dict[str, int | None]) -> bool:
    for table, count in counts.items():
        if table == "printer_schema_migrations":
            continue
        if count:
            return False
    return (counts.get("printer_schema_migrations") or 0) > 0


def only_source_smoke_rows_exist(counts: dict[str, int | None]) -> bool:
    if row_count_sum(counts, SOURCE_TABLES) <= 0:
        return False
    return row_count_sum(counts, SOURCE_ONLY_BLOCKER_TABLES) == 0


def token_rows_look_test_only(db_path: Path) -> bool:
    with connect_read_only(db_path) as connection:
        if not table_exists(connection, "printer_tokens"):
            return False
        rows = connection.execute("SELECT token_mint FROM printer_tokens").fetchall()
    if not rows:
        return False
    markers = ("test", "audit-", "monitor-", "decision-", "mint-solana-test")
    return all(any(marker in (row["token_mint"] or "") for marker in markers) for row in rows)


def classify_operator_db_state(db_path: str | Path | None = None, project_root: str | Path | None = None) -> str:
    resolved = resolve_operator_db_path(db_path, project_root)
    if not resolved.is_file():
        return STATE_NO_DB
    counts = get_core_table_counts(resolved, project_root)
    if row_count_sum(counts, PAPER_TABLES) > 0:
        return STATE_PAPER_ROWS
    if row_count_sum(counts, MEMORY_TABLES) > 0:
        return STATE_MEMORY_ROWS
    if only_source_smoke_rows_exist(counts):
        return STATE_SOURCE_ONLY_SMOKE_CHECK
    if counts.get("printer_tokens"):
        return STATE_TEST_ONLY if token_rows_look_test_only(resolved) else STATE_TOKEN_ROWS
    if only_schema_rows_exist(counts):
        return STATE_SCHEMA_ONLY
    if any(count for count in counts.values() if count):
        return STATE_UNCLEAR
    return STATE_UNCLEAR


def memory_has_started(db_path: str | Path | None = None, project_root: str | Path | None = None) -> bool:
    counts = get_core_table_counts(db_path, project_root)
    return row_count_sum(counts, MEMORY_TABLES) > 0


def paper_trading_has_started(db_path: str | Path | None = None, project_root: str | Path | None = None) -> bool:
    counts = get_core_table_counts(db_path, project_root)
    return row_count_sum(counts, PAPER_TABLES) > 0


def runtime_has_started(db_path: str | Path | None = None, project_root: str | Path | None = None) -> bool:
    resolved = resolve_operator_db_path(db_path, project_root)
    if not resolved.is_file():
        return False
    with connect_read_only(resolved) as connection:
        if not table_exists(connection, "printer_scheduler_jobs"):
            return False
        count = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'").fetchone()[0]
    return int(count) > 0


def get_operator_db_status(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_operator_db_path(db_path, project_root)
    exists = resolved.is_file()
    state = classify_operator_db_state(resolved, project_root)
    return {
        "db_path": str(resolved),
        "exists": exists,
        "state_classification": state,
        "table_counts": get_core_table_counts(resolved, project_root) if exists else {},
        "memory_has_started": memory_has_started(resolved, project_root) if exists else False,
        "paper_trading_has_started": paper_trading_has_started(resolved, project_root) if exists else False,
        "runtime_has_started": runtime_has_started(resolved, project_root) if exists else False,
    }
