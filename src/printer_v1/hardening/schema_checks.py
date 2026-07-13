"""Read-only hardening checks for schema, labels, and source shape."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.db.migrate import PROJECT_ROOT
from printer_v1.hardening.contracts import (
    SYNTHETIC_FLOW_STAGE_LABELS,
    VALIDATION_ISSUE_LABELS,
    VALIDATION_RESULT_LABELS,
    VALIDATION_SCOPE_LABELS,
    SyntheticFlowStageLabel,
    ValidationIssueLabel,
    ValidationResultLabel,
    ValidationScopeLabel,
)


def collect_expected_phase_tables() -> list[str]:
    return [
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
        "printer_paper_decision_audits",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
        "printer_paper_audit_reports",
        "printer_operator_review_reports",
        "printer_operator_review_items",
        "printer_validation_runs",
        "printer_validation_items",
    ]


@contextmanager
def _connect(db_path_or_conn: str | Path | sqlite3.Connection):
    if isinstance(db_path_or_conn, sqlite3.Connection):
        yield db_path_or_conn
        return
    connection = sqlite3.connect(db_path_or_conn)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _pass_item(scope: str, stage: str, payload: dict | None = None) -> dict[str, Any]:
    return {
        "validation_scope_label": scope,
        "validation_result_label": ValidationResultLabel.VALIDATION_PASS.value,
        "validation_issue_label": ValidationIssueLabel.VALIDATION_ISSUE_NONE.value,
        "flow_stage_label": stage,
        "item_payload": payload or {},
    }


def _fail_item(scope: str, issue: str, stage: str, payload: dict | None = None) -> dict[str, Any]:
    return {
        "validation_scope_label": scope,
        "validation_result_label": ValidationResultLabel.VALIDATION_FAIL.value,
        "validation_issue_label": issue,
        "flow_stage_label": stage,
        "item_payload": payload or {},
    }


def check_required_tables_exist(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    with _connect(db_path_or_conn) as connection:
        existing = _tables(connection)
    expected = set(collect_expected_phase_tables())
    missing = sorted(expected - existing)
    result = ValidationResultLabel.VALIDATION_FAIL.value if missing else ValidationResultLabel.VALIDATION_PASS.value
    issue = (
        ValidationIssueLabel.VALIDATION_ISSUE_MISSING_TABLE.value
        if missing
        else ValidationIssueLabel.VALIDATION_ISSUE_NONE.value
    )
    return {
        "validation_scope_label": ValidationScopeLabel.VALIDATION_SCHEMA.value,
        "validation_result_label": result,
        "validation_issue_label": issue,
        "flow_stage_label": SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
        "missing_tables": missing,
        "expected_tables": sorted(expected),
    }


def _forbidden_column_names() -> set[str]:
    return {
        "score",
        "confidence",
        "rank",
        "rating",
        "weight",
        "wallet" + "_address",
        "private" + "_key",
        "signed" + "_tx",
        "live" + "_trade",
        "transaction" + "_signature",
        "tx" + "_signature",
        "execute" + "_trade",
    }


def check_forbidden_columns_absent(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    forbidden = _forbidden_column_names()
    findings: list[dict[str, str]] = []
    with _connect(db_path_or_conn) as connection:
        for table in sorted(_tables(connection)):
            for column in sorted(_columns(connection, table) & forbidden):
                findings.append({"table": table, "column": column})
    result = ValidationResultLabel.VALIDATION_FAIL.value if findings else ValidationResultLabel.VALIDATION_PASS.value
    issue = (
        ValidationIssueLabel.VALIDATION_ISSUE_FORBIDDEN_COLUMN.value
        if findings
        else ValidationIssueLabel.VALIDATION_ISSUE_NONE.value
    )
    return {
        "validation_scope_label": ValidationScopeLabel.VALIDATION_SCHEMA.value,
        "validation_result_label": result,
        "validation_issue_label": issue,
        "flow_stage_label": SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
        "findings": findings,
    }


def check_validation_tables_exist(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    with _connect(db_path_or_conn) as connection:
        existing = _tables(connection)
    missing = sorted({"printer_validation_runs", "printer_validation_items"} - existing)
    if missing:
        return _fail_item(
            ValidationScopeLabel.VALIDATION_SCHEMA.value,
            ValidationIssueLabel.VALIDATION_ISSUE_MISSING_TABLE.value,
            SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
            {"missing_tables": missing},
        )
    return _pass_item(
        ValidationScopeLabel.VALIDATION_SCHEMA.value,
        SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
        {"tables": ["printer_validation_runs", "printer_validation_items"]},
    )


def check_contract_label_consistency() -> dict[str, Any]:
    groups = {
        "scope": VALIDATION_SCOPE_LABELS,
        "result": VALIDATION_RESULT_LABELS,
        "issue": VALIDATION_ISSUE_LABELS,
        "stage": SYNTHETIC_FLOW_STAGE_LABELS,
    }
    problems = [name for name, labels in groups.items() if len(labels) != len(set(labels))]
    if problems:
        return _fail_item(
            ValidationScopeLabel.VALIDATION_CONTRACTS.value,
            ValidationIssueLabel.VALIDATION_ISSUE_LABEL_MISMATCH.value,
            SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
            {"problem_groups": problems},
        )
    return _pass_item(
        ValidationScopeLabel.VALIDATION_CONTRACTS.value,
        SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
        {"label_groups": sorted(groups)},
    )


_FORBIDDEN_EXECUTABLE_NAMES = {
    "wallet_address",
    "private_key",
    "signed_tx",
    "live_trade",
    "transaction_signature",
    "tx_signature",
    "execute_trade",
    "confidence_score",
    "buy_score",
    "ranking_score",
    "rank_score",
    "score",
    "confidence",
    "embedding",
    "vector",
}

_NETWORK_MODULES = {"requests", "httpx", "aiohttp"}
_RUNTIME_FRAMEWORKS = {
    "celery", "cron", "apscheduler", "fastapi", "flask", "django",
    "react", "vue", "svelte",
}
_BOUNDED_LOOP_NAMES = {
    "max_duration_seconds", "deadline", "_cycle_budget", "max_cycles",
    "max_ticks", "remaining_ticks",
}


def _iter_source_files(project_root: str | Path | None = None) -> Iterable[Path]:
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    yield from (root / "src" / "printer_v1").rglob("*.py")


def _allowed_scan_file(path: Path) -> bool:
    normalized = str(path).replace("\\", "/")
    return normalized.endswith("src/printer_v1/contracts/rules.py")


def _parsed_source_files(
    project_root: str | Path | None,
) -> Iterable[tuple[Path, ast.AST | None, str | None]]:
    for path in _iter_source_files(project_root):
        if _allowed_scan_file(path):
            continue
        try:
            yield path, ast.parse(path.read_text(encoding="utf-8")), None
        except (OSError, SyntaxError, UnicodeError) as exc:
            yield path, None, f"source_parse_failed:{type(exc).__name__}"


def _is_source_adapter(path: Path) -> bool:
    normalized = str(path).replace("\\", "/")
    return "/src/printer_v1/sources/" in f"/{normalized}"


def _imported_module(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name.lower() if node.names else None
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").lower()
    return None


def _scan_live_capabilities(project_root: str | Path | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, tree, parse_error in _parsed_source_files(project_root):
        if parse_error:
            findings.append({"path": str(path), "term": parse_error})
            continue
        assert tree is not None
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id.lower() in _FORBIDDEN_EXECUTABLE_NAMES:
                found.add(node.id.lower())
            elif isinstance(node, ast.Attribute) and node.attr.lower() in _FORBIDDEN_EXECUTABLE_NAMES:
                found.add(node.attr.lower())
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and not _is_source_adapter(path):
                module = _imported_module(node) or ""
                imports_urllib_request = (
                    isinstance(node, ast.ImportFrom)
                    and module == "urllib"
                    and any(alias.name == "request" for alias in node.names)
                )
                if (
                    module.split(".", 1)[0] in _NETWORK_MODULES
                    or module == "urllib.request"
                    or imports_urllib_request
                ):
                    found.add(f"direct_network_import:{module}")
        findings.extend({"path": str(path), "term": term} for term in sorted(found))
    return findings


def _scan_runtime_capabilities(project_root: str | Path | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, tree, parse_error in _parsed_source_files(project_root):
        if parse_error:
            findings.append({"path": str(path), "term": parse_error})
            continue
        assert tree is not None
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = (_imported_module(node) or "").split(".", 1)[0]
                if module in _RUNTIME_FRAMEWORKS:
                    found.add(f"runtime_framework:{module}")
            elif (
                isinstance(node, ast.While)
                and isinstance(node.test, ast.Constant)
                and node.test.value is True
            ):
                loop_names = {
                    child.id for child in ast.walk(node) if isinstance(child, ast.Name)
                }
                has_termination = any(
                    isinstance(child, (ast.Break, ast.Return, ast.Raise))
                    for child in ast.walk(node)
                )
                if not has_termination or not (loop_names & _BOUNDED_LOOP_NAMES):
                    found.add("unbounded_while_true")
        findings.extend({"path": str(path), "term": term} for term in sorted(found))
    return findings


def check_no_live_capability_terms_in_source(project_root: str | Path | None = None) -> dict[str, Any]:
    findings = _scan_live_capabilities(project_root)
    if findings:
        return _fail_item(
            ValidationScopeLabel.VALIDATION_CONTRACTS.value,
            ValidationIssueLabel.VALIDATION_ISSUE_LIVE_CAPABILITY_FOUND.value,
            SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
            {"findings": findings},
        )
    return _pass_item(
        ValidationScopeLabel.VALIDATION_CONTRACTS.value,
        SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
        {"findings": []},
    )


def check_no_runtime_loop_terms_in_source(project_root: str | Path | None = None) -> dict[str, Any]:
    findings = _scan_runtime_capabilities(project_root)
    if findings:
        return _fail_item(
            ValidationScopeLabel.VALIDATION_CONTRACTS.value,
            ValidationIssueLabel.VALIDATION_ISSUE_RUNTIME_LOOP_FOUND.value,
            SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
            {"findings": findings},
        )
    return _pass_item(
        ValidationScopeLabel.VALIDATION_CONTRACTS.value,
        SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value,
        {"findings": []},
    )


def build_schema_hardening_report(
    db_path_or_conn: str | Path | sqlite3.Connection,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    checks = [
        check_required_tables_exist(db_path_or_conn),
        check_forbidden_columns_absent(db_path_or_conn),
        check_validation_tables_exist(db_path_or_conn),
        check_contract_label_consistency(),
        check_no_live_capability_terms_in_source(project_root),
        check_no_runtime_loop_terms_in_source(project_root),
    ]
    passed = all(check["validation_result_label"] == ValidationResultLabel.VALIDATION_PASS.value for check in checks)
    return {
        "validation_scope_label": ValidationScopeLabel.VALIDATION_SCHEMA.value,
        "validation_result_label": (
            ValidationResultLabel.VALIDATION_PASS.value
            if passed
            else ValidationResultLabel.VALIDATION_FAIL.value
        ),
        "synthetic_only": True,
        "paper_only": True,
        "checks": checks,
    }
