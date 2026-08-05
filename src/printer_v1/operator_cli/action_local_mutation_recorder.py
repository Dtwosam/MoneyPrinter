"""Bounded action-local mutation identity recorder for ordinary WINDOW_15M.

Existing write owners emit inserted/updated row identities when known. No global
SQLite tracing. Unknown identities remain ``UNKNOWN_NOT_ATTRIBUTABLE``.
"""

from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any, Mapping, MutableMapping


class ActionLocalMutationRecorder:
    """Thread-safe, append-only identity ledger for one campaign action."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._inserted: dict[str, list[Any]] = {}
        self._updated: dict[str, list[Any]] = {}
        self._unknown_tables: set[str] = set()

    def record_insert(self, table: str, row_id: Any) -> None:
        """Record one inserted row identity. Never invent an identity."""
        if row_id is None:
            self.record_unknown(table)
            return
        key = str(table)
        with self._lock:
            bucket = self._inserted.setdefault(key, [])
            if row_id not in bucket:
                bucket.append(row_id)

    def record_update(self, table: str, row_id: Any) -> None:
        """Record one updated row identity. Never invent an identity."""
        if row_id is None:
            self.record_unknown(table)
            return
        key = str(table)
        with self._lock:
            bucket = self._updated.setdefault(key, [])
            if row_id not in bucket:
                bucket.append(row_id)

    def record_unknown(self, table: str) -> None:
        """Mark a table mutation as known-to-have-occurred but unattributable."""
        with self._lock:
            self._unknown_tables.add(str(table))

    def freeze(self) -> dict[str, object]:
        """Return an immutable snapshot of recorded identities."""
        with self._lock:
            return {
                "inserted_rows": deepcopy(self._inserted),
                "updated_rows": deepcopy(self._updated),
                "unknown_tables": sorted(self._unknown_tables),
            }

    def inserted_row_ids(self) -> Mapping[str, list[Any]]:
        with self._lock:
            return deepcopy(self._inserted)

    def updated_row_ids(self) -> Mapping[str, list[Any]]:
        with self._lock:
            return deepcopy(self._updated)

    def authoritative_write_count(self) -> int | None:
        """Numeric write count only when every write has an identity."""
        with self._lock:
            if self._unknown_tables:
                return None
            total = 0
            for ids in self._inserted.values():
                total += len(ids)
            for ids in self._updated.values():
                total += len(ids)
            return total


# Process-local campaign action recorder (mirrors _ACTION_RUN_CONTEXT pattern).
_ACTIVE_MUTATION_RECORDER: ActionLocalMutationRecorder | None = None
_RECORDER_LOCK = Lock()


def install_action_local_mutation_recorder(
    recorder: ActionLocalMutationRecorder | None = None,
) -> ActionLocalMutationRecorder:
    """Install (or replace) the active campaign mutation recorder."""
    global _ACTIVE_MUTATION_RECORDER
    active = recorder if recorder is not None else ActionLocalMutationRecorder()
    with _RECORDER_LOCK:
        _ACTIVE_MUTATION_RECORDER = active
    return active


def clear_action_local_mutation_recorder() -> None:
    global _ACTIVE_MUTATION_RECORDER
    with _RECORDER_LOCK:
        _ACTIVE_MUTATION_RECORDER = None


def get_action_local_mutation_recorder() -> ActionLocalMutationRecorder | None:
    with _RECORDER_LOCK:
        return _ACTIVE_MUTATION_RECORDER


def emit_insert(table: str, row_id: Any) -> None:
    recorder = get_action_local_mutation_recorder()
    if recorder is not None:
        recorder.record_insert(table, row_id)


def emit_update(table: str, row_id: Any) -> None:
    recorder = get_action_local_mutation_recorder()
    if recorder is not None:
        recorder.record_update(table, row_id)


def emit_unknown(table: str) -> None:
    recorder = get_action_local_mutation_recorder()
    if recorder is not None:
        recorder.record_unknown(table)


__all__ = [
    "ActionLocalMutationRecorder",
    "clear_action_local_mutation_recorder",
    "emit_insert",
    "emit_unknown",
    "emit_update",
    "get_action_local_mutation_recorder",
    "install_action_local_mutation_recorder",
]
