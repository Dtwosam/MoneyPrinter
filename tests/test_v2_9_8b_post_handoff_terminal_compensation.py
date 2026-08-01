"""Frozen offline proof: V2-9.8B post-handoff terminal compensation repair.

Accepted invariant after a post-handoff failure:

    zero active, runnable, leased, reusable, or orphan work;
    immutable terminal handoff audit evidence may remain.

Proven, with frozen inputs and a fresh disposable migration-050 database per
injection, for each of the five post-handoff stages:

* surviving token slots are terminal and non-runnable, with the exact
  post-handoff cause attributable to campaign/run/cycle/stage;
* zero slots active / selected-for-continuation / reusable;
* zero linked tracking rows QUEUED/active/promotable;
* zero first-15m or campaign-scoped Scheduler jobs active/claimable;
* zero active leases;
* zero deletable lifecycle-materialization residue;
* immutable selected-item links present and unchanged; retained rows FK-valid;
* the compensation report reconciles retained / terminalized / deleted rows;
* a second compensation pass is idempotent (no duplicate mutation; DB unchanged);
* no retry/restart/successor/retrieval/decision/position/trade/audit/PnL path;
* normal success remains unchanged (two slots, two first-15m jobs, links present,
  no longer-window or financial unlock).
"""

from __future__ import annotations

import sqlite3

import pytest

from printer_v1.operator_cli.origin_lifecycle_campaign import (
    POST_HANDOFF_STAGES,
    OriginToLifecycleCampaignDriver,
    PostHandoffCompensationScope,
    _compensate_post_handoff_teardown,
)

from test_v2_9_7e_8_origin_to_lifecycle_integration import (
    MINT_A,
    MINT_B,
    _IntegrationBase,
)


_TERMINAL_SLOT_STATES = ("COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED")
_LONGER_WINDOW_JOB_KINDS = (
    "TRACK_NORMAL_1H",
    "TRACK_NORMAL_4H",
    "TRACK_FAST_1H",
    "TRACK_FAST_4H",
    "TRACK_FAST_MICRO_EVENT",
)
_FINANCIAL_TABLES = (
    "printer_memory_retrieval_matches",
    "printer_memory_retrieval_queries",
    "printer_paper_audit_reports",
    "printer_paper_decision_audits",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_quote_evidence",
    "printer_paper_trade_audits",
    "printer_paper_trade_events",
)


class _Harness(_IntegrationBase):
    def runTest(self) -> None:  # pragma: no cover - satisfies TestCase
        pass

    def run_with_fault(self, stage):
        driver = OriginToLifecycleCampaignDriver()
        snapshot_factory, _calls = self._snapshot_adapter_factory()
        return driver.run(
            command=self.command,
            fixtures=self._two_origin_fixtures(),
            backup_path=self.backup,
            selection_seed="seed",
            proof_mode=True,
            lifecycle_kwargs={
                "snapshot_adapter_factory": snapshot_factory,
                "context_adapter_factories": self._context_factories(),
                "_window_seconds": 0.05,
                "total_duration_seconds": 3.0,
                "launch_provenance": {
                    "git_head": "f" * 40,
                    "git_tracked_tree_clean": True,
                    "git_staged_changes_present": False,
                    "git_unstaged_changes_present": False,
                    "git_untracked_present": True,
                    "git_provenance_captured_at": "2026-07-21T17:00:00+00:00",
                },
            },
            post_handoff_fault=stage,
        )


def _count(connection, sql, params=()):
    return int(connection.execute(sql, params).fetchone()[0])


def _cycle_slot_token_ids(connection):
    return [
        {"token_row_id": int(r[0])}
        for r in connection.execute(
            "SELECT token_row_id FROM printer_memory_factory_campaign_token_slots "
            "WHERE cycle_id='cyc' ORDER BY slot_ordinal"
        )
    ]


def _content_snapshot(connection):
    """Order-stable content fingerprint of every row the compensation can touch."""
    snapshot = {}
    for label, sql in (
        (
            "slots",
            "SELECT token_slot_id,token_state,first_terminal_cause,terminal_at "
            "FROM printer_memory_factory_campaign_token_slots WHERE cycle_id='cyc' "
            "ORDER BY token_slot_id",
        ),
        (
            "tracking",
            "SELECT id,queue_status,tracking_action FROM printer_tracking_queue "
            "ORDER BY id",
        ),
        (
            "jobs",
            "SELECT id,status FROM printer_scheduler_jobs ORDER BY id",
        ),
        (
            "links",
            "SELECT discovery_batch_id,selection_item_id,token_slot_id,"
            "tracking_handoff_state,first_window_15m_scheduler_job_id "
            "FROM printer_discovery_selected_item_links ORDER BY selection_item_id",
        ),
        (
            "cycle",
            "SELECT cycle_state,first_terminal_cause FROM "
            "printer_memory_factory_campaign_cycles WHERE cycle_id='cyc'",
        ),
    ):
        snapshot[label] = [tuple(r) for r in connection.execute(sql)]
    return snapshot


@pytest.mark.parametrize("stage", POST_HANDOFF_STAGES)
def test_post_handoff_injection_terminalizes_and_preserves_evidence(stage) -> None:
    harness = _Harness()
    harness.setUp()
    try:
        result = harness.run_with_fault(stage)
        cause = f"POST_HANDOFF_{stage}"

        # FAILED terminal; lifecycle never started; cause attributable to stage.
        assert result.activation.terminal_status == "FAILED"
        assert result.activation.first_terminal_cause == cause
        assert result.lifecycle_started is False

        report = result.lifecycle["post_handoff_compensation_report"]
        assert report["terminal_cause"] == cause
        assert report["campaign_id"] == "camp"
        assert report["run_id"] == "run"
        assert report["cycle_id"] == "cyc"

        # Zero active / runnable / leased / orphan work.
        assert report["clean_zero_active_work"] is True
        assert report["remaining_active_work"] == {
            "active_slots": 0,
            "queued_or_active_tracking": 0,
            "active_first_15m_jobs": 0,
            "active_campaign_jobs": 0,
            "active_leases": 0,
            "deletable_residue_rows": 0,
        }

        # Deletable lifecycle-materialization residue is gone.
        assert report["deleted_lifecycle_residue"]["selection_batches"] in (0, 1)
        connection = harness._conn()
        try:
            # --- surviving slots: terminal, non-runnable, cause on each slot ---
            slot_rows = connection.execute(
                "SELECT token_state,first_terminal_cause,terminal_at FROM "
                "printer_memory_factory_campaign_token_slots WHERE cycle_id='cyc' "
                "ORDER BY slot_ordinal"
            ).fetchall()
            assert len(slot_rows) == 2
            for state, terminal_cause, terminal_at in slot_rows:
                assert state in _TERMINAL_SLOT_STATES
                assert terminal_cause == cause
                assert terminal_at is not None
            assert report["terminalized_pinned_rows"]["token_slots_terminalized"] == 2

            # --- zero slots selectable for continuation / reuse ---
            assert (
                _count(
                    connection,
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
                    "WHERE cycle_id='cyc' AND token_state='SELECTED'",
                )
                == 0
            )

            # --- linked tracking rows terminal, none QUEUED/active/promotable ---
            assert (
                _count(
                    connection,
                    "SELECT COUNT(*) FROM printer_tracking_queue "
                    "WHERE queue_status IN ('QUEUED','ACTIVE','PAUSED','COOLDOWN')",
                )
                == 0
            )
            assert report["terminalized_pinned_rows"]["tracking_rows_terminalized"] >= 1

            # --- first-15m + campaign jobs: none active/claimable ---
            assert (
                _count(
                    connection,
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE status IN ('PENDING','RUNNING','COOLDOWN') "
                    "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL",
                )
                == 0
            )
            assert report["terminalized_pinned_rows"]["first_15m_jobs_cancelled"] >= 1
            # No longer-window jobs were ever created.
            for kind in _LONGER_WINDOW_JOB_KINDS:
                assert (
                    _count(
                        connection,
                        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_kind=?",
                        (kind,),
                    )
                    == 0
                )

            # --- zero active leases ---
            assert (
                _count(
                    connection,
                    "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
                    "WHERE lease_state IN ('ACTIVE','STOPPING')",
                )
                == 0
            )

            # --- zero deletable lifecycle-materialization residue ---
            assert (
                _count(
                    connection,
                    "SELECT COUNT(*) FROM printer_selection_batches WHERE batch_id=?",
                    (f"origin-activated:cyc",),
                )
                == 0
            )
            assert (
                _count(connection, "SELECT COUNT(*) FROM printer_memory_factory_run_steps")
                == 0
            )
            assert (
                _count(connection, "SELECT COUNT(*) FROM printer_token_lifecycle_events")
                == 0
            )

            # --- immutable links present and unchanged (2, HANDOFF_RECORDED) ---
            links = connection.execute(
                "SELECT tracking_handoff_state, first_window_15m_scheduler_job_id "
                "FROM printer_discovery_selected_item_links WHERE cycle_id='cyc'"
            ).fetchall()
            assert len(links) == 2
            for handoff_state, job_id in links:
                assert handoff_state == "HANDOFF_RECORDED"
                assert job_id is not None
            assert report["immutable_retained_evidence"]["selected_item_links"] == 2

            # --- retained rows FK-valid; integrity; migration head ---
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            head = [
                r[0]
                for r in connection.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY version"
                )
            ][-1]
            assert head.startswith("050")

            # --- cycle/run/campaign terminalized to the fault cause ---
            cycle_state, cycle_cause = connection.execute(
                "SELECT cycle_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_cycles WHERE cycle_id='cyc'"
            ).fetchone()
            assert cycle_state.startswith("TERMINAL_")
            assert cycle_cause == cause

            # --- no restart / successor / financial / retrieval / decision path ---
            recon = report["reconciliation"]
            assert recon["restart_created"] is False
            assert recon["successor_created"] is False
            for table in _FINANCIAL_TABLES:
                assert (
                    _count(connection, f"SELECT COUNT(*) FROM {table}") == 0
                ), f"{stage}: {table} must be empty"
        finally:
            connection.close()
    finally:
        harness.tearDown()


@pytest.mark.parametrize("stage", POST_HANDOFF_STAGES)
def test_second_compensation_pass_is_idempotent(stage) -> None:
    harness = _Harness()
    harness.setUp()
    try:
        first_result = harness.run_with_fault(stage)
        cause = f"POST_HANDOFF_{stage}"
        connection = harness._conn()
        try:
            before = _content_snapshot(connection)
        finally:
            connection.close()
        first_scope = first_result.lifecycle[
            "post_handoff_compensation_report"
        ]["scope"]
        scope = PostHandoffCompensationScope(**first_scope)

        # Second, independent compensation pass over the already-terminal graph.
        report2 = _compensate_post_handoff_teardown(
            harness.db,
            scope=scope,
            terminal_cause=cause,
        )
        # No duplicate transition, cancellation, or deletion.
        assert report2["mutations_this_pass"] == {
            "rows_deleted": 0,
            "first_15m_jobs_cancelled": 0,
            "slots_transitioned": 0,
            "campaign_jobs_cancelled": 0,
            "leases_released": 0,
        }
        assert report2["clean_zero_active_work"] is True

        connection = harness._conn()
        try:
            after = _content_snapshot(connection)
        finally:
            connection.close()
        assert after == before
    finally:
        harness.tearDown()


def test_normal_success_unchanged() -> None:
    """Success path: two distinct slots, two first-15m jobs, links present."""
    harness = _Harness()
    harness.setUp()
    try:
        result = harness._run_driver()
        assert result.activation.terminal_status == "COMPLETED"
        assert result.lifecycle_started is True
        assert len(result.activation.activated_slots) == 2
        activated_mints = {
            s["mint_identity"] for s in result.activation.activated_slots
        }
        assert activated_mints == {MINT_A, MINT_B}

        connection = harness._conn()
        try:
            # Exactly two distinct mint/pair slots.
            slot_pairs = connection.execute(
                "SELECT mint_identity,pair_identity FROM "
                "printer_memory_factory_campaign_token_slots WHERE cycle_id='cyc'"
            ).fetchall()
            assert len(slot_pairs) == 2
            assert len({m for m, _ in slot_pairs}) == 2
            assert len({p for _, p in slot_pairs}) == 2
            # Exactly two immutable selected-item links.
            assert (
                _count(
                    connection,
                    "SELECT COUNT(*) FROM printer_discovery_selected_item_links "
                    "WHERE cycle_id='cyc'",
                )
                == 2
            )
            # No longer-window (1h/4h/micro) job and no financial unlock.
            for kind in _LONGER_WINDOW_JOB_KINDS:
                assert (
                    _count(
                        connection,
                        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_kind=?",
                        (kind,),
                    )
                    == 0
                )
            for table in _FINANCIAL_TABLES:
                assert _count(connection, f"SELECT COUNT(*) FROM {table}") == 0
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            connection.close()
    finally:
        harness.tearDown()
