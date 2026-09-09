"""Current Printer V1 capability-sequencing locks.

These are not permanent V1 bans. Retrieval activation and paper decisions are
implemented subsystems, but the active authority keeps them disabled until a
separate deliberate capability change updates both policy and code.

Read-only memory comparison remains allowed. Mutation, Scheduler activation, and
paper-decision output must pass these locks.
"""

from __future__ import annotations


RETRIEVAL_ACTIVATION_ENABLED = False
PAPER_DECISIONS_ENABLED = False

RETRIEVAL_TARGET_TABLES = frozenset(
    {
        "printer_memory_retrieval_queries",
        "printer_memory_retrieval_matches",
    }
)
PAPER_DECISION_TARGET_TABLES = frozenset(
    {
        "printer_paper_decisions",
        "printer_paper_decision_audits",
    }
)


class CapabilityLockedError(RuntimeError):
    """Raised when code attempts to activate a currently locked capability."""

    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(self.code)


def require_retrieval_activation_enabled() -> None:
    if not RETRIEVAL_ACTIVATION_ENABLED:
        raise CapabilityLockedError("RETRIEVAL_ACTIVATION_LOCKED")


def require_paper_decisions_enabled() -> None:
    if not PAPER_DECISIONS_ENABLED:
        raise CapabilityLockedError("PAPER_DECISIONS_LOCKED")


def require_scheduler_target_enabled(target_table: str | None) -> None:
    target = "" if target_table is None else str(target_table)
    if target in RETRIEVAL_TARGET_TABLES:
        require_retrieval_activation_enabled()
    if target in PAPER_DECISION_TARGET_TABLES:
        require_paper_decisions_enabled()
