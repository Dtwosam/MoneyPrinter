"""Focused V2-9.8B post-repair full-run WINDOW_15M accounting/terminal tests.

Disposable databases only. These prove the exact campaign-window ownership,
campaign Scheduler ownership, identity-bearing six-unit evidence, non-vacuous
owner/action-local equality, terminal-slot semantics, quality consistency, the
canonical report, and the acceptance gate — without running any operational
campaign or mutating the authoritative database.
"""

from __future__ import annotations

from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_ownership import (
    CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT,
    CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT,
    CampaignOwnershipError,
    bind_authoritative_run_id,
    campaign_scheduler_work_id,
    create_campaign_run,
    create_cycle_with_two_slots,
    project_campaign_scheduler_job as _accepted_project_campaign_scheduler_job,
    register_campaign_window_close,
)
from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
    REQUIRED_LIFECYCLE_STAGE_KINDS,
    VERDICT_BLOCKED_UNSAFE,
    VERDICT_PASS,
    build_full_run_terminal_report,
    evaluate_campaign_acceptance_gate,
    evaluate_quality_consistency,
    resolve_campaign_slot_terminal_disposition,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignSixUnitError,
    CampaignSixUnitOwner,
    EVIDENCE_KIND_V2,
    build_campaign_stage_id,
    reconcile_owner_to_action_local,
    reconstruct_six_unit_totals_from_evidence,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import (
    LifecycleReservationIdentity,
    LocalValidationIdentity,
    MeasuredTransportLedger,
    SchedulerWorkIdentity,
    build_transport_identity,
)


NOW = "2026-07-31T00:00:00+00:00"
CAMPAIGN = "campaign-a"
CONFIG = "configuration-a"
RUN = "run-a"
CYCLE = "cycle-a"
FACTORY_RUN = "factory-run-a"


def project_campaign_scheduler_job(
    connection, *, campaign_id, run_id, cycle_id, factory_run_id,
    token_slot_id, window_id, scheduler_job_id, job_kind, deadline_at,
    terminal_state=None, terminal_cause=None, now=None,
):
    """Exercise the accepted scope-aware wrapper through the historical fixture API."""
    del terminal_state, terminal_cause, now
    ordinal = int(str(token_slot_id).rsplit("-", 1)[-1])
    result = _accepted_project_campaign_scheduler_job(
        connection,
        scheduler_work_id=campaign_scheduler_work_id(campaign_id, scheduler_job_id),
        campaign_id=campaign_id, run_id=run_id, cycle_id=cycle_id,
        factory_run_id=factory_run_id, token_slot_id=token_slot_id,
        window_id=window_id,
        work_intent=f"{job_kind}|factory_run={factory_run_id}|job={scheduler_job_id}",
        deadline_at=deadline_at, scheduler_job_id=scheduler_job_id,
        stage_id=build_campaign_stage_id(
            campaign_id=campaign_id, run_id=run_id, cycle_id=cycle_id,
            stage_kind=f"WINDOW_15M_SLOT_{ordinal}", stage_sequence=ordinal + 1,
        ),
        target_category="CAMPAIGN_WINDOW", target_identity=window_id,
    )
    return {
        "registered": bool(result.created),
        "idempotent": not bool(result.created),
        "scheduler_work_id": result.scheduler_work_id,
    }


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class _FullRunFixture(unittest.TestCase):
    """Builds a disposable two-token terminal WINDOW_15M graph."""

    def setUp(self) -> None:
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.db = Path(self.temp.name) / "full-run.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id=CAMPAIGN,
            configuration_id=CONFIG,
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-a",
            proof_source_db_identity="source-a",
            policy_version="v2-9.8b",
        )
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self.context = OperationalLifecycleOwnershipContext(
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            cycle_id=CYCLE,
            configuration_id=CONFIG,
            factory_run_id=FACTORY_RUN,
        )
        self._seed_graph()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    # -- seeding ---------------------------------------------------------- #
    def _slot(self, slot: int, token: int) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{slot}",
            "slot_ordinal": slot,
            "token_identity": f"token-{token}",
            "token_row_id": token,
            "mint_identity": f"mint-{token}",
            "pair_identity": f"pair-{token}",
            "pair_row_id": token,
            "lifecycle_identity": f"lifecycle-{token}",
        }

    def _seed_graph(self) -> None:
        with self.conn:
            for token in (1, 2):
                self.conn.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (token, f"mint-{token}"),
                )
                self.conn.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
                    (token, token, f"pair-{token}"),
                )
                # Two closed WINDOW_15M memory rows with blank cycle_id.
                self.conn.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,memory_status,
                        data_quality_label,do_not_train
                    ) VALUES (?,?,?,'WINDOW_15M',?,?,?,?)""",
                    (
                        token, token, token, NOW,
                        "CLEAN_MEMORY" if token == 1 else "PARTIAL_MEMORY",
                        "CLEAN_DATA" if token == 1 else "ACCEPTABLE_PARTIAL_DATA",
                        0 if token == 1 else 1,
                    ),
                )
            # Factory run + campaign run bound to it.
            self.conn.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at
                ) VALUES (?,'COMPLETED','WINDOW_15M','PROOF_ONLY','h','{}',?)""",
                (FACTORY_RUN, NOW),
            )
        create_campaign_run(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, run_ordinal=1, now=NOW
        )
        bind_authoritative_run_id(
            self.conn, campaign_run_id=RUN, factory_run_id=FACTORY_RUN, now=NOW
        )
        create_cycle_with_two_slots(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            cycle_ordinal=1, slots=(self._slot(1, 1), self._slot(2, 2)), now=NOW,
        )
        self.job_ids: dict[int, dict[str, list[int]]] = {}
        with self.conn:
            job_id = 0
            for token in (1, 2):
                snapshot_jobs: list[int] = []
                for snap in range(8):
                    job_id += 1
                    self.conn.execute(
                        """INSERT INTO printer_scheduler_jobs(
                            id,job_name,job_kind,status,scheduled_for,finished_at
                        ) VALUES (?,?,?,'SUCCEEDED',?,?)""",
                        (job_id, f"snap-{token}-{snap}", "SNAPSHOT", NOW, NOW),
                    )
                    self.conn.execute(
                        """INSERT INTO printer_memory_factory_run_steps(
                            run_id,step_key,step_kind,step_status,token_id,pair_id,
                            scheduler_job_id,memory_window_id
                        ) VALUES (?,?,?,'SUCCEEDED',?,?,?,?)""",
                        (
                            FACTORY_RUN, f"t{token}_snapshot_{snap:02d}", "SNAPSHOT",
                            token, token, job_id, token,
                        ),
                    )
                    snapshot_jobs.append(job_id)
                # One close job/step per token.
                job_id += 1
                self.conn.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        id,job_name,job_kind,status,scheduled_for,finished_at
                    ) VALUES (?,?,?,'SUCCEEDED',?,?)""",
                    (job_id, f"close-{token}", "MEMORY_WINDOW_CLOSE", NOW, NOW),
                )
                close_cursor = self.conn.execute(
                    """INSERT INTO printer_memory_factory_run_steps(
                        run_id,step_key,step_kind,step_status,token_id,pair_id,
                        scheduler_job_id,memory_window_id
                    ) VALUES (?,?,?,'SUCCEEDED',?,?,?,?)""",
                    (
                        FACTORY_RUN, f"t{token}_window_close", "WINDOW_CLOSE",
                        token, token, job_id, token,
                    ),
                )
                self.job_ids[token] = {
                    "snapshot_jobs": snapshot_jobs,
                    "close_job": job_id,
                    "close_step_id": int(close_cursor.lastrowid),
                }

    def _register_both_windows(self) -> list[dict[str, object]]:
        results = []
        for token in (1, 2):
            results.append(
                register_campaign_window_close(
                    self.conn,
                    campaign_id=CAMPAIGN,
                    run_id=RUN,
                    cycle_id=CYCLE,
                    factory_run_id=FACTORY_RUN,
                    token_slot_id=f"slot-{token}",
                    window_id=f"window-15m-{token}",
                    close_step_id=self.job_ids[token]["close_step_id"],
                    memory_window_row_id=token,
                    root_15m_lifecycle_identity=f"lifecycle-{token}",
                    checkpoint_cutoff=NOW,
                    terminal_window_state="CLEAN_PROMOTED" if token == 1 else "DIRTY",
                    terminal_cause="window_closed_clean" if token == 1 else "window_closed_dirty",
                    now=NOW,
                )
            )
        return results


class WindowRegistrationTests(_FullRunFixture):
    def test_two_token_completion_creates_two_campaign_owned_windows(self) -> None:
        results = self._register_both_windows()
        self.assertTrue(all(r["registered"] for r in results))
        rows = self.conn.execute(
            """SELECT window_id, token_row_id, pair_row_id, window_state
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_15M'
               ORDER BY window_id""",
            (CAMPAIGN, RUN, CYCLE),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["token_row_id"] for r in rows], [1, 2])
        self.assertEqual(
            [r["window_state"] for r in rows], ["CLEAN_PROMOTED", "DIRTY"]
        )
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_both_memory_windows_carry_exact_cycle_identity(self) -> None:
        self._register_both_windows()
        cycles = self.conn.execute(
            "SELECT id, cycle_id FROM printer_memory_windows ORDER BY id"
        ).fetchall()
        self.assertEqual([r["cycle_id"] for r in cycles], [CYCLE, CYCLE])

    def test_exact_repeat_registration_is_idempotent(self) -> None:
        self._register_both_windows()
        again = self._register_both_windows()
        self.assertTrue(all(not r["registered"] and r["idempotent"] for r in again))
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows"
            ).fetchone()[0],
            2,
        )

    def test_ownership_conflict_fails_closed(self) -> None:
        self._register_both_windows()
        with self.assertRaises(CampaignOwnershipError) as ctx:
            register_campaign_window_close(
                self.conn,
                campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                factory_run_id=FACTORY_RUN, token_slot_id="slot-2",
                window_id="window-15m-1",  # already owned by token 1/slot-1
                close_step_id=self.job_ids[2]["close_step_id"],
                memory_window_row_id=2,
                root_15m_lifecycle_identity="lifecycle-2",
                checkpoint_cutoff=NOW, terminal_window_state="DIRTY",
                terminal_cause="c", now=NOW,
            )
        self.assertIn(CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT, str(ctx.exception))

    def test_close_step_outside_factory_run_fails_closed(self) -> None:
        with self.assertRaises(CampaignOwnershipError) as ctx:
            register_campaign_window_close(
                self.conn,
                campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                factory_run_id="some-other-factory-run", token_slot_id="slot-1",
                window_id="window-15m-1",
                close_step_id=self.job_ids[1]["close_step_id"],
                memory_window_row_id=1,
                root_15m_lifecycle_identity="lifecycle-1",
                checkpoint_cutoff=NOW, terminal_window_state="CLEAN_PROMOTED",
                terminal_cause="c", now=NOW,
            )
        self.assertIn(CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT, str(ctx.exception))


class SchedulerProjectionTests(_FullRunFixture):
    def _project_all_lifecycle_jobs(self) -> list[dict[str, object]]:
        self._register_both_windows()
        projected = []
        for token in (1, 2):
            window_id = f"window-15m-{token}"
            for job in self.job_ids[token]["snapshot_jobs"]:
                projected.append(
                    project_campaign_scheduler_job(
                        self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                        factory_run_id=FACTORY_RUN, token_slot_id=f"slot-{token}",
                        window_id=window_id, scheduler_job_id=job, job_kind="SNAPSHOT",
                        deadline_at=NOW, terminal_state="SUCCEEDED",
                        terminal_cause="snapshot_done", now=NOW,
                    )
                )
            projected.append(
                project_campaign_scheduler_job(
                    self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                    factory_run_id=FACTORY_RUN, token_slot_id=f"slot-{token}",
                    window_id=window_id,
                    scheduler_job_id=self.job_ids[token]["close_job"],
                    job_kind="MEMORY_WINDOW_CLOSE", deadline_at=NOW,
                    terminal_state="SUCCEEDED", terminal_cause="close_done", now=NOW,
                )
            )
        return projected

    def test_all_factory_scheduler_jobs_have_exact_campaign_ownership(self) -> None:
        projected = self._project_all_lifecycle_jobs()
        self.assertEqual(len(projected), 18)
        # Every projection references an existing scheduler job id, one row each.
        owned = self.conn.execute(
            """SELECT scheduler_job_id, COUNT(*) c
               FROM printer_memory_factory_campaign_scheduler_work
               WHERE campaign_id=? GROUP BY scheduler_job_id""",
            (CAMPAIGN,),
        ).fetchall()
        self.assertEqual(len(owned), 18)
        self.assertTrue(all(r["c"] == 1 for r in owned))
        # No duplicate Scheduler jobs were created.
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0],
            18,
        )
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_scheduler_projection_is_idempotent_and_conflict_fails_closed(self) -> None:
        self._register_both_windows()
        first = project_campaign_scheduler_job(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            factory_run_id=FACTORY_RUN, token_slot_id="slot-1",
            window_id="window-15m-1", scheduler_job_id=self.job_ids[1]["close_job"],
            job_kind="MEMORY_WINDOW_CLOSE", deadline_at=NOW, terminal_state="SUCCEEDED",
            terminal_cause="close_done", now=NOW,
        )
        self.assertTrue(first["registered"])
        again = project_campaign_scheduler_job(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            factory_run_id=FACTORY_RUN, token_slot_id="slot-1",
            window_id="window-15m-1", scheduler_job_id=self.job_ids[1]["close_job"],
            job_kind="MEMORY_WINDOW_CLOSE", deadline_at=NOW, terminal_state="SUCCEEDED",
            terminal_cause="close_done", now=NOW,
        )
        self.assertTrue(again["idempotent"] and not again["registered"])
        # Same job projected into a different window/slot fails closed.
        with self.assertRaises(CampaignOwnershipError) as ctx:
            project_campaign_scheduler_job(
                self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                factory_run_id=FACTORY_RUN, token_slot_id="slot-2",
                window_id="window-15m-2",
                scheduler_job_id=self.job_ids[1]["close_job"],
                job_kind="MEMORY_WINDOW_CLOSE", deadline_at=NOW,
                terminal_state="SUCCEEDED", terminal_cause="c", now=NOW,
            )
        self.assertIn("competing campaign/scope/stage/target/linkage", str(ctx.exception))


# --------------------------------------------------------------------------- #
# Identity-bearing six-unit evidence + action-local equality
# --------------------------------------------------------------------------- #

def _stage_transport(stage: str, ordinal: int, target: str):
    return build_transport_identity(
        stage=stage, source_name="dexscreener_pair", endpoint_owner="dexscreener",
        governed_request_kind="pair", method_or_endpoint="/pair", within_request_ordinal=ordinal,
        target_category="pair", target_identity=target, response_bytes=64, normalized_rows=1,
    )


def _build_owner_and_action_local(
    *, seal_all_stages: bool = True
) -> tuple[CampaignSixUnitOwner, CampaignActionLocalLedger]:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    action_local = CampaignActionLocalLedger(
        campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE, lifecycle_started=True
    )
    stage_kinds = list(REQUIRED_LIFECYCLE_STAGE_KINDS)
    if not seal_all_stages:
        stage_kinds = stage_kinds[:-1]  # omit CAMPAIGN_TERMINAL_RECONCILIATION
    for sequence, stage_kind in enumerate(stage_kinds, start=1):
        stage_id = build_campaign_stage_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            stage_kind=stage_kind, stage_sequence=sequence,
        )
        transport = _stage_transport(stage_kind, sequence, f"tgt-{sequence}")
        ledger = MeasuredTransportLedger(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
        ledger.record_transport(transport)
        sched = SchedulerWorkIdentity(
            stage_id=stage_id, scheduler_job_id=sequence, job_kind="SNAPSHOT",
            target_category="window", target_identity=f"w-{sequence}",
        )
        reservation = LifecycleReservationIdentity(
            stage_id=stage_id, factory_run_id=FACTORY_RUN, token_id=1, pair_id=1,
            window_kind="WINDOW_15M", reservation_ordinal=sequence,
        )
        validation = LocalValidationIdentity(
            stage_id=stage_id, subject_identity=f"step-{sequence}",
            validation_kind="CADENCE", validation_ordinal=sequence,
        )
        sealed = seal_campaign_stage_evidence(
            stage_id=stage_id, stage_kind=stage_kind, stage_sequence=sequence,
            stage_terminal_status="COMPLETED", campaign_id=CAMPAIGN, run_id=RUN,
            cycle_id=CYCLE, ledger=ledger,
            scheduler_work_identities=[sched],
            lifecycle_reservation_identities=[reservation],
            local_validation_identities=[validation],
        )
        owner.ingest_stage_evidence(sealed)
        # Action-local observes the exact same identities at execution boundaries.
        action_local.observe_transport(transport)
        action_local.observe_scheduler_work(sched)
        action_local.observe_lifecycle_reservation(reservation)
        action_local.observe_local_validation(validation)
    owner.close()
    return owner, action_local


class IdentityBearingEvidenceTests(unittest.TestCase):
    def test_full_run_evidence_reconstructs_exact_totals(self) -> None:
        owner, _ = _build_owner_and_action_local()
        evidence = owner.durable_evidence()
        self.assertEqual(evidence["evidence_kind"], EVIDENCE_KIND_V2)
        totals = reconstruct_six_unit_totals_from_evidence(evidence)
        n = len(REQUIRED_LIFECYCLE_STAGE_KINDS)
        self.assertEqual(totals["SCHEDULER_WORK_ITEM"], n)
        self.assertEqual(totals["LIFECYCLE_RESERVED_TRANSPORT_OPERATION"], n)
        self.assertEqual(totals["LOCAL_VALIDATION_STEP"], n)
        self.assertEqual(totals["SOURCE_TRANSPORT_OPERATION"], n)
        # Totals derive from unique identities, not free integers.
        self.assertEqual(
            totals["SCHEDULER_WORK_ITEM"], len(evidence["scheduler_work_identities"])
        )

    def test_independent_action_local_equality_succeeds(self) -> None:
        owner, action_local = _build_owner_and_action_local()
        result = reconcile_owner_to_action_local(
            owner, action_local_ledger=action_local,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        self.assertTrue(result["equal"], result["mismatch_reason"])
        self.assertTrue(result["lifecycle_started"])

    def test_missing_action_local_lifecycle_evidence_fails_closed(self) -> None:
        owner, _ = _build_owner_and_action_local()
        result = reconcile_owner_to_action_local(
            owner, lifecycle_started=True,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        self.assertFalse(result["equal"])
        self.assertEqual(
            result["mismatch_reason"], "ACTION_LOCAL_LIFECYCLE_EVIDENCE_MISSING"
        )

    def test_count_identity_duplicate_and_stage_conflicts_fail_closed(self) -> None:
        # (a) count/identity mismatch: action-local drops one scheduler identity.
        owner, action_local = _build_owner_and_action_local()
        action_local.scheduler_work_identities.pop()
        mismatch = reconcile_owner_to_action_local(
            owner, action_local_ledger=action_local,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        self.assertFalse(mismatch["equal"])
        self.assertIn("SCHEDULER_WORK_ITEM", mismatch["mismatch_reason"])

        # (b) duplicate action-local identity.
        owner2, action_local2 = _build_owner_and_action_local()
        action_local2.scheduler_work_identities.append(
            dict(action_local2.scheduler_work_identities[0])
        )
        dup = reconcile_owner_to_action_local(
            owner2, action_local_ledger=action_local2,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        self.assertFalse(dup["equal"])

        # (c) missing mandatory sealed lifecycle stage.
        owner3, action_local3 = _build_owner_and_action_local(seal_all_stages=False)
        missing_stage = reconcile_owner_to_action_local(
            owner3, action_local_ledger=action_local3,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        self.assertFalse(missing_stage["equal"])
        self.assertIn(
            "MISSING_MANDATORY_LIFECYCLE_STAGE", missing_stage["mismatch_reason"]
        )

        # (d) duplicate stage id ingested twice fails closed in the owner.
        owner4 = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
        stage_id = build_campaign_stage_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            stage_kind="WINDOW_15M_SLOT_1", stage_sequence=1,
        )
        ledger = MeasuredTransportLedger(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
        ledger.record_transport(_stage_transport("WINDOW_15M_SLOT_1", 1, "t"))
        sealed = seal_campaign_stage_evidence(
            stage_id=stage_id, stage_kind="WINDOW_15M_SLOT_1", stage_sequence=1,
            stage_terminal_status="COMPLETED", campaign_id=CAMPAIGN, run_id=RUN,
            cycle_id=CYCLE, ledger=ledger,
        )
        owner4.ingest_stage_evidence(sealed)
        with self.assertRaises(CampaignSixUnitError):
            owner4.ingest_stage_evidence(sealed)


# --------------------------------------------------------------------------- #
# Terminal-slot semantics + quality consistency
# --------------------------------------------------------------------------- #

class TerminalAndQualityTests(unittest.TestCase):
    def test_completed_owned_lifecycle_does_not_become_manual_review(self) -> None:
        result = resolve_campaign_slot_terminal_disposition(
            lifecycle_started=True, owned_terminal_window_state="DIRTY",
            queue_disposition="COOLDOWN",
        )
        self.assertEqual(result["slot_terminal_state"], "COOLDOWN")
        self.assertTrue(result["pass_eligible"])
        # No lifecycle -> MANUAL_REVIEW is still allowed.
        no_lifecycle = resolve_campaign_slot_terminal_disposition(
            lifecycle_started=False, owned_terminal_window_state=None,
            queue_disposition=None,
        )
        self.assertEqual(no_lifecycle["slot_terminal_state"], "MANUAL_REVIEW")
        self.assertFalse(no_lifecycle["pass_eligible"])

    def test_partial_or_dirty_window_cannot_create_clean_episode(self) -> None:
        dirty = evaluate_quality_consistency(
            memory_status="PARTIAL_MEMORY", data_quality_label="DIRTY_DATA",
            do_not_train=1, proposed_episode_kind="WINDOW_15M_CLEAN_MEMORY",
        )
        self.assertFalse(dirty["clean_episode_allowed"])
        self.assertFalse(dirty["quality_consistent"])
        self.assertTrue(dirty["lifecycle_completion_valid"])
        # Legacy CLEAN_MEMORY label may create a clean episode.
        clean = evaluate_quality_consistency(
            memory_status="CLEAN_MEMORY", data_quality_label="CLEAN_DATA",
            do_not_train=0, proposed_episode_kind="WINDOW_15M_CLEAN_MEMORY",
        )
        self.assertTrue(clean["clean_episode_allowed"])
        self.assertTrue(clean["quality_consistent"])
        # E2Z clean-candidate shape: PARTIAL_MEMORY + CLEAN_DATA + do_not_train=0.
        e2z_candidate = evaluate_quality_consistency(
            memory_status="PARTIAL_MEMORY", data_quality_label="CLEAN_DATA",
            do_not_train=0, proposed_episode_kind="WINDOW_15M_CLEAN_MEMORY",
        )
        self.assertTrue(e2z_candidate["clean_episode_allowed"])
        self.assertTrue(e2z_candidate["quality_consistent"])


# --------------------------------------------------------------------------- #
# Canonical report + acceptance gate + zero-side-effect replay
# --------------------------------------------------------------------------- #

class ReportAndGateTests(_FullRunFixture):
    def _full_terminal_report(self) -> dict[str, object]:
        self._register_both_windows()
        # Project the 18 lifecycle scheduler jobs.
        for token in (1, 2):
            window_id = f"window-15m-{token}"
            for job in self.job_ids[token]["snapshot_jobs"]:
                project_campaign_scheduler_job(
                    self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                    factory_run_id=FACTORY_RUN, token_slot_id=f"slot-{token}",
                    window_id=window_id, scheduler_job_id=job, job_kind="SNAPSHOT",
                    deadline_at=NOW, terminal_state="SUCCEEDED",
                    terminal_cause="snapshot_done", now=NOW,
                )
            project_campaign_scheduler_job(
                self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                factory_run_id=FACTORY_RUN, token_slot_id=f"slot-{token}",
                window_id=window_id, scheduler_job_id=self.job_ids[token]["close_job"],
                job_kind="MEMORY_WINDOW_CLOSE", deadline_at=NOW, terminal_state="SUCCEEDED",
                terminal_cause="close_done", now=NOW,
            )
        owner, action_local = _build_owner_and_action_local()
        reconciliation = reconcile_owner_to_action_local(
            owner, action_local_ledger=action_local,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        selected_tokens = [
            {"token_id": t, "pair_id": t, "token_mint": f"mint-{t}",
             "pair_address": f"pair-{t}", "token_slot_id": f"slot-{t}"}
            for t in (1, 2)
        ]
        slot_dispositions = [
            resolve_campaign_slot_terminal_disposition(
                lifecycle_started=True,
                owned_terminal_window_state="CLEAN_PROMOTED" if t == 1 else "DIRTY",
                queue_disposition="COOLDOWN",
            )
            for t in (1, 2)
        ]
        quality_results = [
            {**evaluate_quality_consistency(
                memory_status="CLEAN_MEMORY" if t == 1 else "PARTIAL_MEMORY",
                data_quality_label="CLEAN_DATA" if t == 1 else "ACCEPTABLE_PARTIAL_DATA",
                do_not_train=0 if t == 1 else 1,
                proposed_episode_kind=None,
            ), "window_id": f"window-15m-{t}"}
            for t in (1, 2)
        ]
        return build_full_run_terminal_report(
            self.conn, context=self.context, execution_id="exec-a", supervision_id=1,
            launch_git_provenance=_provenance(), db_target_identity="isolated-a",
            selected_tokens=selected_tokens, runtime_terminal_status="TERMINAL_COMPLETED",
            owner_evidence=owner.durable_evidence(), six_unit_totals=owner.six_unit_totals(),
            action_local_evidence={
                "ledger_id": action_local.ledger_id,
                "transport_identities": action_local.transport_identities,
                "scheduler_work_identities": action_local.scheduler_work_identities,
                "lifecycle_reservation_identities": action_local.lifecycle_reservation_identities,
                "local_validation_identities": action_local.local_validation_identities,
                "scheduler_transition_coverage": action_local.scheduler_transition_coverage(),
            },
            reconciliation=reconciliation,
            per_token_outcomes=[
                {"token_id": t, "pair_id": t, "terminal_status": "WINDOW_CLOSED",
                 "tracking_disposition": "COOLDOWN"} for t in (1, 2)
            ],
            slot_dispositions=slot_dispositions, quality_results=quality_results,
            zero_active_scheduler_jobs=0,
            forbidden_capability_deltas={
                "retrieval_queries": 0, "paper_decisions": 0, "paper_trades": 0,
                "window_1h_unlocked": 0,
            },
        )

    def test_canonical_report_includes_both_exact_token_window_outcomes(self) -> None:
        report = self._full_terminal_report()
        selection = report["selection_and_lifecycle"]
        self.assertEqual(sorted(selection["terminal_window_ids"]),
                         ["window-15m-1", "window-15m-2"])
        self.assertEqual(selection["selected_token_count"], 2)
        self.assertEqual(len(selection["per_token_outcomes"]), 2)
        gate = evaluate_campaign_acceptance_gate(report)
        # Helper-built, non-persisted reports no longer satisfy repaired PASS.
        self.assertEqual(gate["verdict"], VERDICT_BLOCKED_UNSAFE)
        self.assertFalse(gate["pass"])

    def test_gate_blocks_unsafe_when_one_window_missing(self) -> None:
        # Only register one window -> lifecycle started but incomplete ownership.
        register_campaign_window_close(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            factory_run_id=FACTORY_RUN, token_slot_id="slot-1",
            window_id="window-15m-1", close_step_id=self.job_ids[1]["close_step_id"],
            memory_window_row_id=1, root_15m_lifecycle_identity="lifecycle-1",
            checkpoint_cutoff=NOW, terminal_window_state="CLEAN_PROMOTED",
            terminal_cause="c", now=NOW,
        )
        owner, action_local = _build_owner_and_action_local()
        reconciliation = reconcile_owner_to_action_local(
            owner, action_local_ledger=action_local,
            required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        )
        report = build_full_run_terminal_report(
            self.conn, context=self.context, execution_id="exec-a", supervision_id=1,
            launch_git_provenance=_provenance(), db_target_identity="isolated-a",
            selected_tokens=[
                {"token_id": t, "pair_id": t, "token_slot_id": f"slot-{t}"}
                for t in (1, 2)
            ],
            runtime_terminal_status="TERMINAL_COMPLETED",
            owner_evidence=owner.durable_evidence(), six_unit_totals=owner.six_unit_totals(),
            action_local_evidence={
                "ledger_id": action_local.ledger_id,
                "scheduler_transition_coverage": action_local.scheduler_transition_coverage(),
            },
            reconciliation=reconciliation, per_token_outcomes=[],
            slot_dispositions=[
                resolve_campaign_slot_terminal_disposition(
                    lifecycle_started=True, owned_terminal_window_state="CLEAN_PROMOTED",
                    queue_disposition="COOLDOWN"),
                resolve_campaign_slot_terminal_disposition(
                    lifecycle_started=True, owned_terminal_window_state=None,
                    queue_disposition=None),
            ],
            quality_results=[], zero_active_scheduler_jobs=0,
            forbidden_capability_deltas={"retrieval_queries": 0},
        )
        gate = evaluate_campaign_acceptance_gate(report)
        self.assertEqual(gate["verdict"], VERDICT_BLOCKED_UNSAFE)
        self.assertFalse(gate["pass"])

    def test_report_only_replay_is_exact_identity_zero_side_effect(self) -> None:
        report = self._full_terminal_report()
        # Snapshot durable state before replay.
        def _counts() -> tuple[int, ...]:
            return tuple(
                self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "printer_memory_factory_campaign_windows",
                    "printer_memory_factory_campaign_scheduler_work",
                    "printer_scheduler_jobs",
                    "printer_source_requests",
                    "printer_source_responses",
                    "printer_memory_retrieval_queries",
                    "printer_paper_decisions",
                    "printer_paper_trade_events",
                )
            )
        before = _counts()
        # Replay: rebuild the report from durable rows only (read-only).
        replay = build_full_run_terminal_report(
            self.conn, context=self.context, execution_id="exec-a", supervision_id=1,
            launch_git_provenance=_provenance(), db_target_identity="isolated-a",
            selected_tokens=report["selection_and_lifecycle"]["selected_tokens"],
            runtime_terminal_status="TERMINAL_COMPLETED",
            owner_evidence=report["full_run_accounting"]["owner_action_local_reconciliation"].get("diagnostics", {}),
            action_local_evidence=report["full_run_accounting"]["action_local_evidence"],
            six_unit_totals=report["full_run_accounting"]["six_unit_totals"],
            reconciliation=report["full_run_accounting"]["owner_action_local_reconciliation"],
            per_token_outcomes=report["selection_and_lifecycle"]["per_token_outcomes"],
            slot_dispositions=report["selection_and_lifecycle"]["slot_dispositions"],
            quality_results=report["selection_and_lifecycle"]["quality_results"],
            zero_active_scheduler_jobs=0,
            forbidden_capability_deltas=report["terminal_safety"]["forbidden_capability_deltas"],
        )
        after = _counts()
        self.assertEqual(before, after)
        self.assertEqual(
            replay["selection_and_lifecycle"]["terminal_window_ids"],
            report["selection_and_lifecycle"]["terminal_window_ids"],
        )
        self.assertEqual(
            replay["full_run_accounting"]["six_unit_totals"],
            report["full_run_accounting"]["six_unit_totals"],
        )

    def test_retrieval_and_financial_deltas_remain_zero(self) -> None:
        report = self._full_terminal_report()
        deltas = report["terminal_safety"]["forbidden_capability_deltas"]
        self.assertTrue(report["terminal_safety"]["zero_forbidden_deltas"])
        self.assertTrue(all(v == 0 for v in deltas.values()))
        # No locked-capability rows were created anywhere in the flow.
        for table in (
            "printer_memory_retrieval_queries", "printer_paper_decisions",
            "printer_paper_positions", "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            self.assertEqual(
                self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
            )


if __name__ == "__main__":
    unittest.main()
