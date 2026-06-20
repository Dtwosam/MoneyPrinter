"""Deterministic output helpers for one-shot operator commands."""

from __future__ import annotations

import json
from typing import Any, Mapping


def _json_safe(payload: Any) -> Any:
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def format_json_output(payload: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe(dict(payload)), indent=2, sort_keys=True)


def format_counts_table(counts: Mapping[str, int | None]) -> str:
    if not counts:
        return "No table counts available."
    width = max(len(name) for name in counts)
    return "\n".join(f"{name.ljust(width)}  {counts[name]}" for name in sorted(counts))


def format_status_summary(status_payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"DB Path: {status_payload.get('db_path')}",
            f"Exists: {status_payload.get('exists')}",
            f"State: {status_payload.get('state_classification')}",
            f"Memory started: {status_payload.get('memory_has_started')}",
            f"Paper trading started: {status_payload.get('paper_trading_has_started')}",
            f"Runtime started: {status_payload.get('runtime_has_started')}",
        ]
    )


def format_migration_summary(migration_payload: Mapping[str, Any]) -> str:
    missing = migration_payload.get("missing_migrations") or []
    return "\n".join(
        [
            f"DB Path: {migration_payload.get('db_path')}",
            f"Exists: {migration_payload.get('exists')}",
            f"Applied migrations: {migration_payload.get('applied_count')}",
            f"Latest migration: {migration_payload.get('latest_migration')}",
            f"Missing migrations: {', '.join(missing) if missing else 'None'}",
        ]
    )


def format_readiness_summary(readiness_payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"Readiness: {readiness_payload.get('readiness_label')}",
            f"DB State: {readiness_payload.get('db_state_classification')}",
            f"Latest migration: {readiness_payload.get('latest_migration')}",
            f"Runtime started: {readiness_payload.get('runtime_has_started')}",
            f"Memory started: {readiness_payload.get('memory_has_started')}",
            f"Paper trading started: {readiness_payload.get('paper_trading_has_started')}",
        ]
    )


def format_text_output(payload: Mapping[str, Any]) -> str:
    if "readiness_label" in payload:
        return format_readiness_summary(payload)
    if "table_counts" in payload:
        return format_status_summary(payload)
    if "counts" in payload:
        return format_counts_table(payload["counts"])
    if "applied_migrations" in payload or "missing_migrations" in payload:
        return format_migration_summary(payload)
    lines = []
    for key in sorted(payload):
        value = payload[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(_json_safe(value), sort_keys=True)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)
