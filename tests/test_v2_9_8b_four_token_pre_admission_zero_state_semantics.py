"""Focused offline regression for migration-055 pre-admission zero-state semantics.

This test reads only the canonical zero-state query from production source and
executes it against disposable in-memory SQLite. It makes no source request,
runs no Printer process, and touches no authoritative database.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sqlite3
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
ZERO_STATE_GATE = (
    REPO_ROOT
    / "src"
    / "printer_v1"
    / "operator_cli"
    / "four_token_proof_zero_state_gate.py"
)

RETAINED_TERMINAL_STATES = (
    "NO_PAIR",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
    "CONSUMED",
)
BLOCKING_STATES = ("PLANNED", "RUNNING", "PAIR_READY")


def _pre_admission_zero_state_query() -> str:
    tree = ast.parse(ZERO_STATE_GATE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id != "_ZERO_STATE_QUERIES":
            continue
        queries = ast.literal_eval(node.value)
        return dict(queries)["pre_admission_discovery_attempts"]
    raise AssertionError("canonical _ZERO_STATE_QUERIES assignment not found")


def _project_state(state: str) -> tuple[int, int]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE printer_pre_admission_discovery_attempts ("
            "attempt_state TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO printer_pre_admission_discovery_attempts(attempt_state) "
            "VALUES (?)",
            (state,),
        )
        query = _pre_admission_zero_state_query()
        projected = int(connection.execute(query).fetchone()[0])
        retained = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
            ).fetchone()[0]
        )
        return projected, retained
    finally:
        connection.close()


class FourTokenPreAdmissionZeroStateSemanticsTests(unittest.TestCase):
    def test_retained_terminal_history_does_not_project_blocking_ownership(self) -> None:
        for state in RETAINED_TERMINAL_STATES:
            with self.subTest(attempt_state=state):
                projected, retained = _project_state(state)
                self.assertEqual(projected, 0)
                self.assertEqual(retained, 1)

    def test_active_or_unconsumed_pair_authority_still_blocks(self) -> None:
        for state in BLOCKING_STATES:
            with self.subTest(attempt_state=state):
                projected, retained = _project_state(state)
                self.assertEqual(projected, 1)
                self.assertEqual(retained, 1)

    def test_unexpected_state_fails_closed(self) -> None:
        projected, retained = _project_state("UNEXPECTED_FUTURE_STATE")
        self.assertEqual(projected, 1)
        self.assertEqual(retained, 1)


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
