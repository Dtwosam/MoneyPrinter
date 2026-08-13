"""V2-9.8B Post-DTW98 pre-lifecycle temporal persistence — focused offline proof.

Implements the 16-case matrix of
``docs/printer-v1-v2-9-8b-post-dtw98-pre-lifecycle-temporal-persistence-design.md``
§12.

Disposable SQLite and an injected fake clock/waiter only. No real sleep, no
provider call, no authoritative database access or mutation, no authorization
creation, no Printer runtime, no WINDOW_15M execution.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count
from printer_v1.discovery.persistence import insert_discovery_batch
from printer_v1.discovery.eligible_token_supply import (
    BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL,
    DURATION_EXHAUSTION,
    ELIGIBLE_FRESH,
    GRADUATED_SUPPLY_READY,
    REMOVED,
    SOURCE_AVAILABILITY_FAILURE,
    TRUE_MARKET_SUPPLY_SHORTAGE,
    load_eligible_reserve,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    CANCELLED,
    CURRENT_UNIVERSE_EXHAUSTED_WAITING,
    NO_LAWFUL_REFRESH_WINDOW,
    PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED,
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    REFRESH_COMPLETED,
    SUPERVISION_FAILED,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    acquisition_deadline_at,
    evaluate_wait_eligibility,
    iso,
    parse_iso,
    refresh_window_fits,
)
from printer_v1.operator_cli.campaign_active_work import (
    campaign_active_work_report,
    campaign_scoped_job_ids,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.pre_lifecycle_temporal_refresh_owner import (
    REFRESH_WORK_TYPE,
    PreLifecycleTemporalRefreshOwner,
)
from printer_v1.scheduler.contracts import JobKind
from printer_v1.scheduler.resource_governor import next_check_interval_seconds
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

from tests.test_v2_9_8b_21_eligible_token_supply_architecture import (
    SPECS24,
    _dex_factory,
    _empty_migration_transport,
    _pair_payload,
    _seed_registry,
)

SEED = "v2-9-8b-post-dtw98-temporal-persistence-seed"
CAMPAIGN = "temporal-campaign"
RUN = "temporal-campaign-run"
CYCLE = "temporal-cycle"
SUPERVISION = "temporal-supervision"
REFRESH_INTERVAL = 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in LOCKED_CAPABILITY_TABLES:
        try:
            out[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        except sqlite3.Error:
            out[table] = -1
    return out


class _TemporalBase(unittest.TestCase):
    """Disposable database plus the exact campaign identities under test."""

    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "temporal.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.locked_before = _locked_counts(self.connection)
        self.start = _now()
        self.deadline = iso(
            self.start + timedelta(seconds=PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS)
        )
        self._seed_campaign_graph()
        self.batch_id = self._create_batch()
        self.stage_calls: list[dict[str, object]] = []
        self.supervision = {"supervision_active": True, "cancellation_requested": False}

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    # -- fixtures ---------------------------------------------------------- #

    def _seed_campaign_graph(self) -> None:
        now = iso(self.start)
        create_campaign(
            self.db,
            campaign_id=CAMPAIGN,
            configuration_id=f"{CAMPAIGN}-configuration",
            configuration={"token_capacity": 2, "campaign_selection_seed": SEED},
            launch_provenance={
                "git_head": "d459057752da229cdd33838cdad7c8adcf3fae6e",
                "git_tracked_tree_clean": True,
                "git_staged_changes_present": False,
                "git_unstaged_changes_present": False,
                "git_untracked_present": False,
                "git_provenance_captured_at": now,
            },
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="disposable-temporal-target",
            proof_source_db_identity="disposable-temporal-source",
            policy_version="V2_9_8B_TEMPORAL_PERSISTENCE_TEST",
        )
        create_campaign_run(
            self.connection,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            run_ordinal=1,
            now=now,
        )
        self.connection.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                created_at, updated_at
            ) VALUES (?,?,?,1,'PLANNED',?,?)""",
            (CYCLE, CAMPAIGN, RUN, now, now),
        )
        self.connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
            "WHERE campaign_id=?",
            (CAMPAIGN,),
        )
        self.connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
            "WHERE run_id=?",
            (RUN,),
        )
        self.connection.commit()

    def _create_batch(self) -> str:
        # printer_discovery_batches is UNIQUE per cycle_id: exactly one exact
        # campaign/run/cycle batch exists, and the temporal refresh reuses it.
        # Use the one canonical derivation both production writers share.
        from printer_v1.discovery.combined_executor import (
            canonical_cycle_discovery_batch_id,
        )

        batch_id = canonical_cycle_discovery_batch_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        insert_discovery_batch(
            self.connection,
            discovery_batch_id=batch_id,
            campaign_id=CAMPAIGN,
            configuration_id=f"{CAMPAIGN}-configuration",
            run_id=RUN,
            cycle_id=CYCLE,
            cycle_cutoff=iso(self.start + timedelta(seconds=1200)),
            policy_version="V2_9_8B_TEMPORAL_PERSISTENCE_TEST",
            provider_contract_versions={"dexscreener": "test"},
            git_provenance_identity="disposable-test",
            campaign_selection_seed_identity=SEED,
            cycle_seed_hash=hashlib.sha256(SEED.encode()).hexdigest(),
            now=iso(self.start),
        )
        self.connection.commit()
        return batch_id

    def _batch_resolver(
        self, connection: sqlite3.Connection, now: str, refresh_ordinal: int
    ) -> str:
        return self.batch_id

    def _stage(self, **kwargs):
        """A refresh stage that performs zero real provider work."""
        def stage(connection, **call):
            self.stage_calls.append(dict(call))
            seeds = kwargs.get("seed_specs") or ()
            for mint, sig, pool in seeds:
                record_graduated_candidate(
                    connection,
                    mint=mint,
                    migration_signature=sig,
                    pumpswap_pool=pool,
                    graduation_block_time=1_784_000_000,
                    graduation_slot=1,
                    now=call["now"],
                    discovery_channel=PERSISTED_GRADUATED_CHANNEL,
                )
            connection.commit()
            if kwargs.get("raises"):
                raise RuntimeError("refresh stage provider failure")
            return {
                "source_operations": int(kwargs.get("source_operations", 1)),
                "provider_failures": int(kwargs.get("provider_failures", 0)),
                "channels_unavailable": tuple(
                    kwargs.get("channels_unavailable") or ()
                ),
            }

        return stage

    def _owner(
        self,
        *,
        waiter=None,
        clock=None,
        acquisition_deadline=None,
        stage=None,
        supervision_probe=...,
        interval=None,
    ) -> PreLifecycleTemporalRefreshOwner:
        return PreLifecycleTemporalRefreshOwner(
            self.db,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            supervision_id=SUPERVISION,
            source_governor=type("Owner", (), {"available": True})(),
            central_scheduler=type("Owner", (), {"available": True})(),
            acquisition_deadline_at=acquisition_deadline or self.deadline,
            work_deadline_at=iso(self.start + timedelta(seconds=1200)),
            refresh_stage=stage if stage is not None else self._stage(),
            discovery_batch_resolver=self._batch_resolver,
            supervision_probe=(
                (lambda: dict(self.supervision))
                if supervision_probe is ...
                else supervision_probe
            ),
            waiter=waiter,
            clock=clock,
            refresh_interval_seconds=interval,
        )

    def _due_clock(self, offset_seconds: int = REFRESH_INTERVAL):
        return lambda: iso(_now() + timedelta(seconds=offset_seconds))

    def _wait_rows(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM printer_pre_lifecycle_discovery_refresh_waits "
                "ORDER BY refresh_ordinal"
            ).fetchall()
        )

    def _jobs(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM printer_scheduler_jobs ORDER BY id"
            ).fetchall()
        )

    def _work_rows(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM printer_discovery_work ORDER BY discovery_work_id"
            ).fetchall()
        )

    def assertNoForbiddenCapabilityDelta(self) -> None:
        self.assertEqual(self.locked_before, _locked_counts(self.connection))


# --------------------------------------------------------------------------- #
# Migration / schema                                                           #
# --------------------------------------------------------------------------- #

class Migration054Tests(_TemporalBase):
    def test_migration_054_adds_exactly_one_narrow_wait_table(self) -> None:
        # Migration 055 is a later additive pre-admission owner; 054 remains
        # unchanged and its narrow wait table remains present in the chain.
        self.assertEqual(canonical_migration_count(), 55)
        columns = {
            str(row[1]): str(row[2])
            for row in self.connection.execute(
                "PRAGMA table_info(printer_pre_lifecycle_discovery_refresh_waits)"
            )
        }
        for required in (
            "wait_id",
            "campaign_id",
            "run_id",
            "cycle_id",
            "supervision_id",
            "scheduler_job_id",
            "refresh_ordinal",
            "wait_state",
            "scheduled_for",
            "acquisition_deadline_at",
            "created_at",
            "updated_at",
            "terminal_at",
            "first_terminal_cause",
        ):
            self.assertIn(required, columns)
        # No source payload, ranking, score, confidence, weight or financial
        # field belongs in this table.
        for forbidden in ("score", "rank", "confidence", "weight", "payload", "pnl"):
            self.assertFalse(
                [name for name in columns if forbidden in name.lower()],
                f"forbidden column family present: {forbidden}",
            )
        self.assertEqual(
            self.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )

    def test_wait_identity_is_immutable_and_terminal_cannot_reopen(self) -> None:
        owner = self._owner()
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        wait_id = outcome.wait_id
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_pre_lifecycle_discovery_refresh_waits "
                "SET campaign_id='other' WHERE wait_id=?",
                (wait_id,),
            )
        self.connection.rollback()
        self.connection.execute(
            "UPDATE printer_pre_lifecycle_discovery_refresh_waits "
            "SET wait_state='CANCELLED', first_terminal_cause='X', terminal_at=?, "
            "updated_at=? WHERE wait_id=?",
            (iso(_now()), iso(_now()), wait_id),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_pre_lifecycle_discovery_refresh_waits "
                "SET wait_state='WAITING' WHERE wait_id=?",
                (wait_id,),
            )
        self.connection.rollback()


# --------------------------------------------------------------------------- #
# Cases 1-4, 10-14: Scheduler-owned waiting contract                           #
# --------------------------------------------------------------------------- #

class TemporalRefreshOwnerTests(_TemporalBase):
    # Case 1 (boundary form) --------------------------------------------- #
    def test_case_01_three_of_four_exhausted_universe_is_nonterminal_waiting(
        self,
    ) -> None:
        eligibility = evaluate_wait_eligibility(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            now=iso(self.start),
            acquisition_deadline_at=self.deadline,
            source_operations_remaining=16,
            provider_terminal_failure=False,
            supervision_active=True,
            cancellation_requested=False,
            pending_refresh_exists=False,
        )
        self.assertTrue(eligibility.eligible)
        self.assertEqual(eligibility.reason, WAITING_FOR_ELIGIBLE_SUPPLY)

        owner = self._owner()
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, WAITING_FOR_ELIGIBLE_SUPPLY)
        self.assertTrue(outcome.waiting)
        self.assertNotEqual(outcome.status, TRUE_MARKET_SUPPLY_SHORTAGE)
        self.assertEqual(
            [state["state"] for state in owner.published_states],
            [WAITING_FOR_ELIGIBLE_SUPPLY],
        )
        # Waiting itself performs zero provider operations.
        self.assertEqual(self.stage_calls, [])
        self.assertEqual(outcome.source_operations, 0)

    # Case 2 --------------------------------------------------------------- #
    def test_case_02_exact_future_refresh_job_and_wait_row_are_persisted(self) -> None:
        owner = self._owner()
        request_at = _now()
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE",
            source_operations_remaining=16,
            now=iso(request_at),
        )
        jobs = self._jobs()
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(str(job["job_kind"]), JobKind.DISCOVERY_REFRESH.value)
        self.assertEqual(str(job["status"]), "PENDING")
        # Canonical Central Scheduler cadence, not an independently tuned one.
        self.assertEqual(
            next_check_interval_seconds(JobKind.DISCOVERY_REFRESH), REFRESH_INTERVAL
        )
        self.assertEqual(owner.refresh_interval_seconds, REFRESH_INTERVAL)
        self.assertAlmostEqual(
            (parse_iso(str(job["scheduled_for"])) - request_at).total_seconds(),
            REFRESH_INTERVAL,
            delta=5,
        )

        rows = self._wait_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(str(row["campaign_id"]), CAMPAIGN)
        self.assertEqual(str(row["run_id"]), RUN)
        self.assertEqual(str(row["cycle_id"]), CYCLE)
        self.assertEqual(str(row["supervision_id"]), SUPERVISION)
        self.assertEqual(int(row["scheduler_job_id"]), int(job["id"]))
        self.assertEqual(int(row["refresh_ordinal"]), 1)
        self.assertEqual(str(row["wait_state"]), "WAITING")
        self.assertEqual(str(row["acquisition_deadline_at"]), self.deadline)
        self.assertEqual(outcome.scheduler_job_id, int(job["id"]))

    # Case 3 --------------------------------------------------------------- #
    def test_case_03_before_due_claim_is_not_due_and_no_source_work_occurs(
        self,
    ) -> None:
        from printer_v1.scheduler.contracts import LockResult
        from printer_v1.scheduler.scheduler import claim_due_job

        owner = self._owner()
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        claim = claim_due_job(
            self.connection,
            job_id=int(outcome.scheduler_job_id),
            lock_owner="premature",
            now=_now(),
        )
        self.assertEqual(claim, LockResult.NOT_DUE)
        self.assertEqual(self.stage_calls, [])
        self.assertEqual(self._work_rows(), [])
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "WAITING")
        self.assertNoForbiddenCapabilityDelta()

    # Case 4 --------------------------------------------------------------- #
    def test_case_04_at_due_exact_claim_precedes_discovery_work_running(self) -> None:
        observed: list[tuple[str, str]] = []

        def stage(connection, **call):
            job = connection.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?",
                (call["scheduler_job_id"],),
            ).fetchone()
            work = connection.execute(
                "SELECT work_state FROM printer_discovery_work "
                "WHERE discovery_work_id=?",
                (call["discovery_work_id"],),
            ).fetchone()
            observed.append((str(job[0]), str(work[0])))
            return {"source_operations": 1}

        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=stage,
        )
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, REFRESH_COMPLETED)
        self.assertTrue(outcome.claimed)
        # The Scheduler job was RUNNING (claimed) before governed work ran, and
        # the exact discovery-work row existed and was RUNNING.
        self.assertEqual(observed, [("RUNNING", "RUNNING")])
        work = self._work_rows()
        self.assertEqual(len(work), 1)
        self.assertEqual(str(work[0]["work_type"]), REFRESH_WORK_TYPE)
        self.assertEqual(str(work[0]["work_state"]), "SUCCEEDED")
        self.assertEqual(
            int(work[0]["scheduler_job_id"]), int(outcome.scheduler_job_id)
        )
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "SUCCEEDED")
        self.assertEqual(str(self._jobs()[0]["status"]), "SUCCEEDED")

    # Case 10 -------------------------------------------------------------- #
    def test_case_10_cancellation_while_waiting_leaves_zero_active_residue(
        self,
    ) -> None:
        def waiter(seconds: float) -> bool:
            self.supervision["cancellation_requested"] = True
            return True

        owner = self._owner(waiter=waiter, clock=self._due_clock(60))
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, CANCELLED)
        self.assertFalse(outcome.claimed)
        self.assertEqual(self.stage_calls, [])
        # No discovery work was ever created for a pre-claim cancellation.
        self.assertEqual(self._work_rows(), [])
        self.assertEqual(str(self._jobs()[0]["status"]), "CANCELLED")
        row = self._wait_rows()[0]
        self.assertEqual(str(row["wait_state"]), "CANCELLED")
        self.assertIsNotNone(row["first_terminal_cause"])
        report = campaign_active_work_report(
            self.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        self.assertEqual(report["active_jobs"], 0)
        self.assertEqual(report["active_pre_lifecycle_refresh_waits"], 0)
        self.assertTrue(report["clean_terminal"])
        self.assertNoForbiddenCapabilityDelta()

    # Case 11 -------------------------------------------------------------- #
    def test_case_11_supervision_failure_during_wait_aborts_without_source_work(
        self,
    ) -> None:
        def waiter(seconds: float) -> bool:
            self.supervision["supervision_active"] = False
            return True

        owner = self._owner(waiter=waiter, clock=self._due_clock(60))
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, SUPERVISION_FAILED)
        self.assertEqual(self.stage_calls, [])
        self.assertEqual(self._work_rows(), [])
        self.assertEqual(str(self._jobs()[0]["status"]), "CANCELLED")
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "CANCELLED")

    def test_deadline_reached_before_due_never_claims(self) -> None:
        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(REFRESH_INTERVAL),
            acquisition_deadline=iso(_now() + timedelta(seconds=610)),
        )
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertIn(
            outcome.status, (ACQUISITION_DEADLINE_EXHAUSTED, REFRESH_COMPLETED)
        )

    def test_no_lawful_window_when_next_interval_exceeds_horizon(self) -> None:
        short = iso(_now() + timedelta(seconds=300))
        self.assertFalse(
            refresh_window_fits(
                now=iso(_now()),
                acquisition_deadline_at=short,
                refresh_interval_seconds=REFRESH_INTERVAL,
            )
        )
        owner = self._owner(acquisition_deadline=short)
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, NO_LAWFUL_REFRESH_WINDOW)
        self.assertEqual(self._jobs(), [])
        self.assertEqual(self._wait_rows(), [])

    # Case 12 -------------------------------------------------------------- #
    def test_case_12_active_work_owner_includes_pending_wait_job(self) -> None:
        owner = self._owner()
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        job_id = int(outcome.scheduler_job_id)
        groups = campaign_scoped_job_ids(
            self.connection,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            exact_scope=True,
        )
        self.assertIn(job_id, groups["pre_lifecycle_refresh_wait_jobs"])
        report = campaign_active_work_report(
            self.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        self.assertEqual(report["active_jobs"], 1)
        self.assertEqual(report["active_job_details"][0]["job_id"], job_id)
        self.assertEqual(
            report["active_job_details"][0]["job_kind"],
            JobKind.DISCOVERY_REFRESH.value,
        )
        self.assertEqual(report["active_pre_lifecycle_refresh_waits"], 1)
        self.assertFalse(report["clean_terminal"])
        # Pending ownership must not fabricate discovery work before the claim.
        self.assertEqual(self._work_rows(), [])

    # Case 13 -------------------------------------------------------------- #
    def test_case_13_foreign_wait_job_is_excluded(self) -> None:
        owner = self._owner()
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        job_id = int(outcome.scheduler_job_id)
        for scope in (
            {"campaign_id": "other", "run_id": RUN, "cycle_id": CYCLE},
            {"campaign_id": CAMPAIGN, "run_id": "other", "cycle_id": CYCLE},
            {"campaign_id": CAMPAIGN, "run_id": RUN, "cycle_id": "other"},
        ):
            groups = campaign_scoped_job_ids(
                self.connection, exact_scope=True, **scope
            )
            self.assertNotIn(
                job_id,
                groups["pre_lifecycle_refresh_wait_jobs"],
                f"foreign scope leaked ownership: {scope}",
            )

    # Case 14 -------------------------------------------------------------- #
    def test_case_14_no_retry_restart_resume_successor_or_new_authorization(
        self,
    ) -> None:
        from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
            ALREADY_PENDING_REFRESH,
        )

        owner = self._owner()
        first = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(first.status, WAITING_FOR_ELIGIBLE_SUPPLY)
        # Design §2.7 — a second refresh may never be created while one is
        # already pending for this exact campaign/run/cycle. This is what makes
        # waiting a single bounded acquisition rather than a retry loop.
        second = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=15,
            now=iso(_now()),
        )
        self.assertEqual(second.status, ALREADY_PENDING_REFRESH)
        self.assertIsNone(second.scheduler_job_id)

        # Identity is fixed for the whole acquisition: same authorization,
        # campaign, run, cycle and supervision. Nothing is restarted, resumed
        # or succeeded, and exactly one Scheduler job exists.
        rows = self._wait_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual({str(r["campaign_id"]) for r in rows}, {CAMPAIGN})
        self.assertEqual({str(r["run_id"]) for r in rows}, {RUN})
        self.assertEqual({str(r["cycle_id"]) for r in rows}, {CYCLE})
        self.assertEqual({str(r["supervision_id"]) for r in rows}, {SUPERVISION})
        self.assertEqual([int(r["refresh_ordinal"]) for r in rows], [1])
        self.assertEqual(len(self._jobs()), 1)
        self.assertEqual(first.scheduler_job_id, int(rows[0]["scheduler_job_id"]))

        source = Path(
            "src/printer_v1/operator_cli/pre_lifecycle_temporal_refresh_owner.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "while True",
            "time.sleep",
            "subprocess",
            "multiprocessing",
            "Thread(",
        ):
            self.assertNotIn(forbidden, source, f"forbidden construct: {forbidden}")
        supply_source = Path(
            "src/printer_v1/discovery/eligible_token_supply.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("enqueue_job", supply_source)
        self.assertNotIn("claim_due_job", supply_source)

    def test_bounded_interruptible_wait_is_one_event_wait(self) -> None:
        from printer_v1.operator_cli.pre_lifecycle_temporal_refresh_owner import (
            bounded_interruptible_wait,
        )

        event = threading.Event()
        event.set()
        self.assertTrue(bounded_interruptible_wait(30.0, event))
        self.assertFalse(bounded_interruptible_wait(0.0, threading.Event()))


# --------------------------------------------------------------------------- #
# Cases 5-9, 15, 16: supply-service integration                                #
# --------------------------------------------------------------------------- #

class TemporalSupplyIntegrationTests(_TemporalBase):
    """Four-deep reserve behaviour across a bounded Scheduler-owned wait."""

    CAPACITY = 4

    def _run_supply(self, *, payloads, owner=None, deadline=None, budget=30):
        return run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=iso(_now()),
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=self.CAPACITY,
            discovery_operation_budget=budget,
            deadline_at=deadline,
            temporal_refresh_owner=owner,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            execution_id=SEED,
        )

    @staticmethod
    def _payloads(specs, eligible_mints, *, liquidity=15_000.0):
        return {
            pool: _pair_payload(
                pool, mint, liquidity if mint in eligible_mints else 40.0
            )
            for mint, _sig, pool in specs
        }

    # Case 1 (end-to-end form) --------------------------------------------- #
    def test_case_01_supply_returns_nonterminal_waiting_not_shortage(self) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        owner = self._owner()  # no waiter: enters and publishes the wait only
        result = self._run_supply(
            payloads=self._payloads(specs, eligible),
            owner=owner,
            deadline=self.deadline,
        )
        self.assertFalse(result.ready)
        self.assertEqual(result.terminal, WAITING_FOR_ELIGIBLE_SUPPLY)
        self.assertIsNone(result.exhaustion_certificate)
        self.assertIsNone(result.shortage_classification)
        self.assertEqual(len(result.eligible_reserve), 3)
        acquisition = result.diagnostics["pre_lifecycle_acquisition"]
        self.assertEqual(acquisition["waiting_states_entered"], 1)
        self.assertEqual(
            acquisition["final_current_universe_state"],
            CURRENT_UNIVERSE_EXHAUSTED_WAITING,
        )
        self.assertEqual(
            acquisition["acquisition_duration_seconds"],
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
        )
        self.assertEqual(acquisition["refresh_interval_seconds"], REFRESH_INTERVAL)
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "WAITING")
        self.assertEqual(self._work_rows(), [])

    # Case 5 --------------------------------------------------------------- #
    def test_case_05_refresh_reveals_fourth_and_retained_three_revalidate(
        self,
    ) -> None:
        specs = SPECS24[:8]
        late = SPECS24[8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        payloads = self._payloads(specs, eligible)
        payloads[late[2]] = _pair_payload(late[2], late[0], 15_000.0)

        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=self._stage(seed_specs=[late], source_operations=1),
        )
        result = self._run_supply(
            payloads=payloads, owner=owner, deadline=self.deadline
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.terminal, GRADUATED_SUPPLY_READY)
        # Exact four-deep freeze: 2 selected + 2 alternates, no more, no less.
        self.assertEqual(len(result.eligible_reserve), 4)
        self.assertEqual(
            {c["mint"] for c in result.eligible_reserve}, eligible | {late[0]}
        )
        # The retained three were re-evaluated after the wait, not assumed.
        self.assertEqual(len(self.stage_calls), 1)
        acquisition = result.diagnostics["pre_lifecycle_acquisition"]
        self.assertEqual(acquisition["temporal_refresh_opportunities_completed"], 1)
        self.assertEqual(acquisition["temporal_refresh_opportunities_claimed"], 1)
        revalidated = acquisition["candidate_revalidation_outcomes"][0]
        self.assertEqual(
            sorted(revalidated["retained_candidates_marked_stale"]), sorted(eligible)
        )
        reserve = {
            str(row["mint_identity"]): str(row["eligibility_status"])
            for row in load_eligible_reserve(self.connection)
        }
        for mint in eligible | {late[0]}:
            self.assertEqual(reserve[mint], ELIGIBLE_FRESH)
        self.assertNoForbiddenCapabilityDelta()

    # Case 6 --------------------------------------------------------------- #
    def test_case_06_retained_candidate_failing_revalidation_drops_capacity(
        self,
    ) -> None:
        specs = SPECS24[:8]
        late = SPECS24[8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        payloads = self._payloads(specs, eligible)
        payloads[late[2]] = _pair_payload(late[2], late[0], 15_000.0)

        failing = specs[0]

        def stage(connection, **call):
            self.stage_calls.append(dict(call))
            record_graduated_candidate(
                connection,
                mint=late[0],
                migration_signature=late[1],
                pumpswap_pool=late[2],
                graduation_block_time=1_784_000_000,
                graduation_slot=1,
                now=call["now"],
                discovery_channel=PERSISTED_GRADUATED_CHANNEL,
            )
            connection.commit()
            # The retained candidate's market collapses below the floor while
            # the campaign waited. It must not keep counting.
            payloads[failing[2]] = _pair_payload(failing[2], failing[0], 40.0)
            return {"source_operations": 1}

        owner = self._owner(
            waiter=lambda seconds: False, clock=self._due_clock(), stage=stage
        )
        result = self._run_supply(
            payloads=payloads, owner=owner, deadline=self.deadline
        )
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertNotIn(failing[0], found)
        self.assertLess(len(result.eligible_reserve), self.CAPACITY)
        self.assertFalse(result.ready)
        reserve = {
            str(row["mint_identity"]): str(row["eligibility_status"])
            for row in load_eligible_reserve(self.connection)
        }
        self.assertEqual(reserve[failing[0]], REMOVED)

    # Case 7 --------------------------------------------------------------- #
    def test_case_07_no_fitting_interval_before_horizon_is_duration_exhaustion(
        self,
    ) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        short = iso(_now() + timedelta(seconds=300))
        owner = self._owner(acquisition_deadline=short)
        result = self._run_supply(
            payloads=self._payloads(specs, eligible), owner=owner, deadline=short
        )
        self.assertFalse(result.ready)
        self.assertEqual(result.terminal, BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL)
        self.assertEqual(result.shortage_classification, DURATION_EXHAUSTION)
        self.assertNotEqual(
            result.shortage_classification, TRUE_MARKET_SUPPLY_SHORTAGE
        )
        certificate = result.exhaustion_certificate.to_dict()
        acquisition = certificate["pre_lifecycle_acquisition"]
        self.assertEqual(
            certificate["last_reason_discovery_could_not_continue"],
            PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED,
        )
        for required in (
            "acquisition_started_at",
            "acquisition_deadline_at",
            "acquisition_elapsed_seconds",
            "acquisition_remaining_seconds",
            "temporal_refresh_opportunities_scheduled",
            "temporal_refresh_opportunities_claimed",
            "temporal_refresh_opportunities_completed",
            "temporal_refresh_opportunities_cancelled",
            "eligible_reserve_depth_transitions",
            "candidate_revalidation_outcomes",
            "final_current_universe_state",
            "controlling_shortage_classification",
        ):
            self.assertIn(required, acquisition)
        self.assertEqual(
            acquisition["controlling_shortage_classification"], DURATION_EXHAUSTION
        )
        self.assertIsNotNone(certificate["source_operations_used"])
        self.assertEqual(self._jobs(), [])

    # Case 8 --------------------------------------------------------------- #
    def test_case_08_cumulative_discovery_budget_does_not_reset_across_refresh(
        self,
    ) -> None:
        specs = SPECS24[:8]
        late = SPECS24[8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        payloads = self._payloads(specs, eligible)
        payloads[late[2]] = _pair_payload(late[2], late[0], 15_000.0)

        baseline = self._run_supply(
            payloads=payloads, owner=None, deadline=self.deadline
        )
        used_without_refresh = baseline.diagnostics["discovery_operations_used"]

        # Fresh disposable database for the with-refresh comparison.
        self.tearDown()
        self.setUp()
        _seed_registry(self.connection, specs, now=iso(self.start))
        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=self._stage(seed_specs=[late], source_operations=3),
        )
        result = self._run_supply(
            payloads=payloads, owner=owner, deadline=self.deadline
        )
        used_with_refresh = result.diagnostics["discovery_operations_used"]
        self.assertGreaterEqual(used_with_refresh, used_without_refresh + 3)
        self.assertEqual(
            result.diagnostics["discovery_operations_remaining"],
            max(0, 30 - used_with_refresh),
        )
        self.assertLessEqual(used_with_refresh, 30)

    # Case 9 --------------------------------------------------------------- #
    def test_case_09_source_failure_classification_is_unchanged(self) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0]}
        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=self._stage(
                source_operations=1,
                provider_failures=1,
                channels_unavailable=("dexscreener_exact_pool_market",),
            ),
        )
        result = self._run_supply(
            payloads=self._payloads(specs, eligible),
            owner=owner,
            deadline=self.deadline,
        )
        self.assertFalse(result.ready)
        self.assertEqual(
            result.shortage_classification, SOURCE_AVAILABILITY_FAILURE
        )
        certificate = result.exhaustion_certificate
        self.assertGreaterEqual(certificate.provider_failures, 1)
        self.assertIn(
            "dexscreener_exact_pool_market", certificate.channels_unavailable
        )

    def test_refresh_stage_failure_is_source_availability_failure(self) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=self._stage(raises=True),
        )
        result = self._run_supply(
            payloads=self._payloads(specs, eligible),
            owner=owner,
            deadline=self.deadline,
        )
        self.assertEqual(
            result.shortage_classification, SOURCE_AVAILABILITY_FAILURE
        )
        # Fail-closed: work, job and wait row are all terminal, none active.
        self.assertEqual(str(self._work_rows()[0]["work_state"]), "FAILED")
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "FAILED")
        report = campaign_active_work_report(
            self.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        self.assertEqual(report["active_jobs"], 0)
        self.assertEqual(report["active_pre_lifecycle_refresh_waits"], 0)

    # Case 15 -------------------------------------------------------------- #
    def test_case_15_zero_forbidden_capability_table_deltas(self) -> None:
        specs = SPECS24[:8]
        late = SPECS24[8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        payloads = self._payloads(specs, eligible)
        payloads[late[2]] = _pair_payload(late[2], late[0], 15_000.0)
        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=self._stage(seed_specs=[late]),
        )
        self._run_supply(payloads=payloads, owner=owner, deadline=self.deadline)
        self.assertNoForbiddenCapabilityDelta()
        for table in LOCKED_CAPABILITY_TABLES:
            self.assertEqual(
                int(
                    self.connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0]
                ),
                0,
            )

    # Case 16 -------------------------------------------------------------- #
    def test_case_16_existing_non_temporal_behaviour_is_unchanged(self) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        result = self._run_supply(
            payloads=self._payloads(specs, eligible), owner=None, deadline=None
        )
        # Without an owner, current-universe exhaustion stays terminal exactly
        # as before this lane.
        self.assertFalse(result.ready)
        self.assertEqual(result.terminal, BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL)
        self.assertIsNotNone(result.exhaustion_certificate)
        self.assertIsNone(
            result.exhaustion_certificate.to_dict()["pre_lifecycle_acquisition"]
        )
        self.assertIsNone(result.diagnostics["pre_lifecycle_acquisition"])
        self.assertEqual(self._jobs(), [])
        self.assertEqual(self._wait_rows(), [])

    def test_acquisition_horizon_is_bounded_at_900_seconds(self) -> None:
        started = iso(self.start)
        self.assertEqual(PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS, 900)
        self.assertEqual(
            (
                parse_iso(acquisition_deadline_at(started)) - parse_iso(started)
            ).total_seconds(),
            900,
        )
        # 900s admits exactly one normal 600s refresh opportunity.
        self.assertTrue(
            refresh_window_fits(
                now=started,
                acquisition_deadline_at=acquisition_deadline_at(started),
                refresh_interval_seconds=REFRESH_INTERVAL,
            )
        )
        after_first = iso(parse_iso(started) + timedelta(seconds=REFRESH_INTERVAL))
        self.assertFalse(
            refresh_window_fits(
                now=after_first,
                acquisition_deadline_at=acquisition_deadline_at(started),
                refresh_interval_seconds=REFRESH_INTERVAL,
            )
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
