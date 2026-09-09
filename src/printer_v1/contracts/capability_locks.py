"""Current Printer V1 capability-sequencing locks.

These are not permanent V1 bans. Retrieval, paper decisions, paper positions
and monitoring, paper audits, and paper PnL are implemented subsystems, but the
active authority keeps them disabled until a separate deliberate capability
change updates both policy and code.

Read-only evidence/history inspection remains allowed. Mutation, Scheduler
activation, action/status output, position/monitor output, audit output, and PnL
output must pass the corresponding current-sequencing lock.
"""

from __future__ import annotations


RETRIEVAL_ACTIVATION_ENABLED = False
PAPER_DECISIONS_ENABLED = False
PAPER_POSITIONS_ENABLED = False
PAPER_AUDITS_ENABLED = False
PAPER_PNL_ENABLED = False

OPEN_PAPER_TRADE_MONITOR_JOB_KIND = "OPEN_PAPER_TRADE_MONITOR"

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
PAPER_POSITION_TARGET_TABLES = frozenset(
    {
        "printer_paper_positions",
        "printer_paper_trade_events",
    }
)
PAPER_AUDIT_TARGET_TABLES = frozenset(
    {
        "printer_paper_trade_audits",
        "printer_paper_audit_reports",
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


def require_paper_positions_enabled() -> None:
    if not PAPER_POSITIONS_ENABLED:
        raise CapabilityLockedError("PAPER_POSITIONS_LOCKED")


def require_paper_audits_enabled() -> None:
    if not PAPER_AUDITS_ENABLED:
        raise CapabilityLockedError("PAPER_AUDITS_LOCKED")


def require_paper_pnl_enabled() -> None:
    if not PAPER_PNL_ENABLED:
        raise CapabilityLockedError("PAPER_PNL_LOCKED")


def require_scheduler_target_enabled(target_table: str | None) -> None:
    target = "" if target_table is None else str(target_table)
    if target in RETRIEVAL_TARGET_TABLES:
        require_retrieval_activation_enabled()
    if target in PAPER_DECISION_TARGET_TABLES:
        require_paper_decisions_enabled()
    if target in PAPER_POSITION_TARGET_TABLES:
        require_paper_positions_enabled()
    if target in PAPER_AUDIT_TARGET_TABLES:
        require_paper_audits_enabled()


def require_scheduler_enqueue_enabled(
    job_kind: object,
    target_table: str | None,
) -> None:
    """Fail closed on target- or job-kind-driven locked Scheduler activation."""

    require_scheduler_target_enabled(target_table)
    kind = str(getattr(job_kind, "value", job_kind))
    if kind == OPEN_PAPER_TRADE_MONITOR_JOB_KIND:
        require_paper_positions_enabled()
